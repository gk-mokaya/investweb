from django.db import models
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
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    pay_address = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=50, blank=True, default='')
    provider_reference = models.CharField(max_length=120, blank=True, default='')
    provider_payload = models.JSONField(blank=True, default=dict)
    verification_payload = models.JSONField(blank=True, default=dict)
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
        status_before = None
        if self.pk:
            status_before = Deposit.objects.filter(pk=self.pk).values_list('status', flat=True).first()
        super().save(*args, **kwargs)

        if status_before is None and self.status != 'completed':
            return

        if status_before != self.status:
            from django.utils import timezone
            from wallets.services import credit_wallet
            from accounts.services import create_notification
            from adminpanel.utils import log_action

            if self.status == 'completed':
                credit_wallet(self.wallet, self.amount, 'main', 'deposit', {'deposit_id': self.id})
                if not self.completed_at:
                    Deposit.objects.filter(pk=self.pk).update(completed_at=timezone.now())
                create_notification(
                    self.user,
                    "Deposit completed",
                    f"Your {self.crypto.symbol} deposit of {self.amount} has been completed.",
                    level='success',
                )
            elif self.status == 'rejected':
                create_notification(
                    self.user,
                    "Deposit rejected",
                    "Your deposit could not be completed. Please contact support if this looks wrong.",
                    level='warning',
                )
            elif self.status in {'pending', 'confirming'}:
                create_notification(
                    self.user,
                    "Deposit pending",
                    "Your deposit is awaiting confirmations.",
                    level='info',
                )

            log_action(None, 'deposit_status_updated', 'deposit', self.id, {'status': self.status})

# Create your models here.
