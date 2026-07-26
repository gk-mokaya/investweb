from django.db import models, transaction
from django.contrib.auth.models import User


class Deposit(models.Model):
    METHOD_CHOICES = [
        ('manual', 'Manual'),
        ('automated', 'Automated'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirming', 'Confirming'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey('wallets.Wallet', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    crypto = models.ForeignKey('payments.CryptoCurrency', on_delete=models.PROTECT)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='manual')
    transaction_hash = models.CharField(max_length=255, null=True, blank=True)
    sender_address = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    screenshot = models.FileField(upload_to='deposits/screenshots/', null=True, blank=True)
    investment_request = models.ForeignKey(
        'investments.UserInvestment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_deposits',
    )
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    pay_address = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=50, blank=True, default='')
    provider_reference = models.CharField(max_length=120, blank=True, default='')
    provider_payload = models.JSONField(blank=True, default=dict)
    verification_payload = models.JSONField(blank=True, default=dict)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_deposits',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default='')
    confirmations = models.IntegerField(default=0)
    target_confirmations = models.IntegerField(default=3)
    check_attempts = models.IntegerField(default=0)
    max_check_attempts = models.IntegerField(default=12)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    next_check_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.crypto.symbol} - {self.amount}"

    def save(self, *args, **kwargs):
        if self.pk:
            with transaction.atomic():
                status_before = Deposit.objects.select_for_update().filter(pk=self.pk).values_list('status', flat=True).first()
                super().save(*args, **kwargs)
                self._apply_status_side_effects(status_before)
            return

        status_before = None
        super().save(*args, **kwargs)
        self._apply_status_side_effects(status_before)

    def _apply_status_side_effects(self, status_before):
        if status_before is None and self.status != 'completed':
            return

        if status_before != self.status:
            from django.utils import timezone
            from wallets.services import credit_wallet
            from accounts.services import create_notification
            from adminpanel.utils import log_action
            from investments.services import activate_investment_from_deposit, cancel_pending_investment_request

            if self.status == 'completed':
                credit_wallet(self.wallet, self.amount, 'main', 'deposit', {'deposit_id': self.id})
                if not self.completed_at:
                    self.completed_at = timezone.now()
                    Deposit.objects.filter(pk=self.pk).update(completed_at=self.completed_at)
                detail = f" Review note: {self.review_note}" if self.review_note else ""
                create_notification(
                    self.user,
                    "Deposit completed",
                    f"Your {self.crypto.symbol} deposit of {self.amount} has been approved, credited, and is now linked to your investment request.{detail}",
                    level='success',
                )
                if self.investment_request_id:
                    activate_investment_from_deposit(self.investment_request, deposit=self)
            elif self.status == 'rejected':
                detail = f" Review note: {self.review_note}" if self.review_note else ""
                create_notification(
                    self.user,
                    "Deposit rejected",
                    f"Your deposit was rejected.{detail}",
                    level='warning',
                )
                if self.investment_request_id:
                    cancel_pending_investment_request(
                        self.investment_request,
                        reason='deposit_rejected',
                        deposit=self,
                    )
            elif self.status in {'pending', 'confirming'}:
                create_notification(
                    self.user,
                    "Deposit pending",
                    "Your deposit is awaiting manual review.",
                    level='info',
                )

            log_action(None, 'deposit_status_updated', 'deposit', self.id, {'status': self.status})

# Create your models here.
