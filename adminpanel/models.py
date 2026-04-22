from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('deposit_created', 'Deposit Created'),
        ('deposit_confirmed', 'Deposit Confirmed'),
        ('deposit_completed', 'Deposit Completed'),
        ('deposit_rejected', 'Deposit Rejected'),
        ('deposit_status_updated', 'Deposit Status Updated'),
        ('withdrawal_created', 'Withdrawal Created'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
        ('withdrawal_paid', 'Withdrawal Paid'),
        ('withdrawal_completed', 'Withdrawal Completed'),
        ('withdrawal_status_updated', 'Withdrawal Status Updated'),
        ('investment_created', 'Investment Created'),
        ('profit_applied', 'Profit Applied'),
        ('settings_changed', 'Settings Changed'),
        ('login', 'Login'),
        ('kyc_approved', 'KYC Approved'),
        ('kyc_rejected', 'KYC Rejected'),
    ]

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50, blank=True, default='')
    target_id = models.CharField(max_length=50, blank=True, default='')
    meta = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.action} - {self.created_at:%Y-%m-%d %H:%M}"

# Create your models here.
