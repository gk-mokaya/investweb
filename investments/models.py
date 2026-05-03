from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class InvestmentPlan(models.Model):
    RISK_CHOICES = [
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('aggressive', 'Aggressive'),
    ]

    PAYOUT_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    LIQUIDITY_CHOICES = [
        ('locked', 'Locked'),
        ('partial', 'Partial'),
        ('flexible', 'Flexible'),
    ]

    LOCK_CHOICES = [
        (0, 'No lock'),
        (7, '7 days'),
        (14, '14 days'),
        (30, '30 days'),
        (60, '60 days'),
        (90, '90 days'),
        (180, '180 days'),
    ]
    TIER_CHOICES = [
        ('standard', 'Standard'),
        ('starter', 'Starter'),
        ('basic', 'Basic'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ]

    name = models.CharField(max_length=100)
    plan_tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='standard')
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    daily_roi = models.DecimalField(max_digits=5, decimal_places=2)
    duration_days = models.IntegerField()
    total_return = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True, default='')
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES, default='moderate')
    payout_frequency = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default='daily')
    liquidity_terms = models.CharField(max_length=40, choices=LIQUIDITY_CHOICES, default='locked')
    lock_period_days = models.IntegerField(choices=LOCK_CHOICES, default=0)
    management_fee_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    capital_protection = models.BooleanField(default=True)
    early_withdrawal_fee_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.daily_roi is not None and self.duration_days:
            total = Decimal(self.daily_roi) * Decimal(self.duration_days)
            self.total_return = total.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def theme_class(self) -> str:
        value = (self.plan_tier or self.name or '').lower()
        if 'vip' in value:
            return 'tier-vip'
        if 'premium' in value:
            return 'tier-premium'
        if 'platinum' in value:
            return 'tier-platinum'
        if 'gold' in value:
            return 'tier-gold'
        if 'silver' in value:
            return 'tier-silver'
        if 'starter' in value:
            return 'tier-starter'
        if 'basic' in value:
            return 'tier-basic'
        return 'tier-standard'


class UserInvestment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey('wallets.Wallet', on_delete=models.PROTECT)
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_completed = models.BooleanField(default=False)
    risk_acknowledged = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.plan.name}"


class DailyProfit(models.Model):
    investment = models.ForeignKey(UserInvestment, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('investment', 'date')

    def __str__(self) -> str:
        return f"{self.investment.id} - {self.date}"

# Create your models here.
