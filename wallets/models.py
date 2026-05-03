from decimal import Decimal
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, Q


class Wallet(models.Model):
    WALLET_TYPES = [
        ('primary', 'Primary'),
        ('trading', 'Trading'),
        ('savings', 'Savings'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallets')
    name = models.CharField(max_length=100)
    wallet_type = models.CharField(max_length=20, choices=WALLET_TYPES)
    main_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    bonus_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    profit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(wallet_type='primary'),
                name='uniq_primary_wallet_per_user',
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.user.username}"

    def save(self, *args, **kwargs):
        if self.wallet_type == 'primary':
            if Wallet.objects.filter(user=self.user, wallet_type='primary').exclude(pk=self.pk).exists():
                raise ValueError("User already has a primary wallet")
            self.is_default = True
        else:
            self.is_default = False
        super().save(*args, **kwargs)

    @property
    def total_balance(self) -> Decimal:
        return self.main_balance + self.bonus_balance + self.profit_balance

    @property
    def has_non_bonus_credit(self) -> bool:
        return self.transactions.filter(amount__gt=0).exclude(txn_type='bonus').exists()

    @property
    def withdrawable_balance(self) -> Decimal:
        if not self.has_non_bonus_credit:
            return Decimal('0')
        return self.total_balance

    @property
    def total_deposits(self) -> Decimal:
        total = self.transactions.filter(txn_type='deposit').aggregate(total=Sum('amount'))['total']
        return total or Decimal('0')

    @property
    def total_withdrawals(self) -> Decimal:
        total = self.transactions.filter(txn_type='withdrawal').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return abs(total)


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('investment', 'Investment'),
        ('profit', 'Profit'),
        ('bonus', 'Bonus'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    txn_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    meta = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.txn_type} - {self.amount}"


class WalletTransfer(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    from_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transfers_out')
    to_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transfers_in')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bucket = models.CharField(max_length=12, default='main')
    note = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} transfer {self.amount} ({self.from_wallet_id} -> {self.to_wallet_id})"

# Create your models here.
