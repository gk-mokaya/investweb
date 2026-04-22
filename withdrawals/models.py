from django.db import models
from django.contrib.auth.models import User


class Withdrawal(models.Model):
    METHOD_CHOICES = [
        ('manual', 'Manual'),
        ('automated', 'Automated'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey('wallets.Wallet', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    crypto = models.ForeignKey('payments.CryptoCurrency', on_delete=models.PROTECT)
    wallet_address = models.CharField(max_length=255)
    destination_network = models.CharField(max_length=60, blank=True, default='')
    memo_tag = models.CharField(max_length=120, blank=True, default='')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.crypto.symbol} - {self.amount}"

    def save(self, *args, **kwargs):
        status_before = None
        if self.pk:
            status_before = Withdrawal.objects.filter(pk=self.pk).values_list('status', flat=True).first()
        super().save(*args, **kwargs)

        if status_before is None:
            return

        if status_before != self.status:
            from django.utils import timezone
            from accounts.services import create_notification
            from adminpanel.utils import log_action

            if self.status in {'approved', 'completed', 'rejected'}:
                if not self.processed_at:
                    Withdrawal.objects.filter(pk=self.pk).update(processed_at=timezone.now())

            if self.status in {'approved', 'completed'}:
                try:
                    profile = self.user.userprofile
                    if not profile.has_withdrawn:
                        profile.has_withdrawn = True
                        profile.is_new_user = False
                        profile.save(update_fields=['has_withdrawn', 'is_new_user'])
                except Exception:
                    pass

            if self.status == 'approved':
                create_notification(
                    self.user,
                    "Withdrawal approved",
                    f"Your withdrawal of {self.amount} was approved and is being processed.",
                    level='success',
                )
            elif self.status == 'completed':
                create_notification(
                    self.user,
                    "Withdrawal completed",
                    f"Your withdrawal of {self.amount} has been completed.",
                    level='success',
                )
            elif self.status == 'rejected':
                create_notification(
                    self.user,
                    "Withdrawal rejected",
                    "Your withdrawal was rejected. Please contact support for details.",
                    level='warning',
                )

            log_action(None, 'withdrawal_status_updated', 'withdrawal', self.id, {'status': self.status})

# Create your models here.
