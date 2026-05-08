from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class InvestmentAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='investment_account')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} - Investment Ledger"

    @property
    def active_positions(self):
        return self.positions.filter(is_completed=False)

    @property
    def completed_positions(self):
        return self.positions.filter(is_completed=True)

    @property
    def active_principal(self) -> Decimal:
        total = self.active_positions.aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0')

    @property
    def active_earned(self) -> Decimal:
        total = self.active_positions.aggregate(total=models.Sum('total_earned'))['total']
        return total or Decimal('0')

    @property
    def total_earned(self) -> Decimal:
        total = self.positions.aggregate(total=models.Sum('total_earned'))['total']
        return total or Decimal('0')

    @property
    def current_balance(self) -> Decimal:
        return self.active_principal + self.active_earned

    @property
    def active_positions_count(self) -> int:
        return self.active_positions.count()

    @property
    def completed_positions_count(self) -> int:
        return self.completed_positions.count()


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
    source_plan = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='derived_versions')
    version_number = models.PositiveIntegerField(default=1)
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

    @property
    def version_label(self) -> str:
        return f"v{self.version_number}"

    @property
    def effective_total_return(self) -> Decimal:
        if self.total_return and self.total_return > 0:
            return Decimal(self.total_return).quantize(Decimal('0.01'))
        if self.daily_roi and self.duration_days:
            total = Decimal(self.daily_roi) * Decimal(self.duration_days)
            return total.quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def effective_daily_roi(self) -> Decimal:
        if self.total_return and self.total_return > 0 and self.duration_days:
            daily = Decimal(self.total_return) / Decimal(self.duration_days)
            return daily.quantize(Decimal('0.01'))
        if self.daily_roi:
            return Decimal(self.daily_roi).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        if self.total_return and self.total_return > 0 and self.duration_days:
            daily = Decimal(self.total_return) / Decimal(self.duration_days)
            self.daily_roi = daily.quantize(Decimal('0.01'))
        elif self.daily_roi and self.daily_roi > 0 and self.duration_days:
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
    account = models.ForeignKey(InvestmentAccount, on_delete=models.CASCADE, related_name='positions', null=True, blank=True)
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_completed = models.BooleanField(default=False)
    settled_at = models.DateTimeField(null=True, blank=True)
    risk_acknowledged = models.BooleanField(default=False)
    plan_snapshot_name = models.CharField(max_length=100, blank=True, default='')
    plan_snapshot_tier = models.CharField(max_length=20, blank=True, default='standard')
    plan_snapshot_daily_roi = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    plan_snapshot_total_return = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    plan_snapshot_duration_days = models.IntegerField(default=0)
    plan_snapshot_payout_frequency = models.CharField(max_length=20, blank=True, default='daily')
    plan_snapshot_liquidity_terms = models.CharField(max_length=40, blank=True, default='locked')
    plan_snapshot_lock_period_days = models.IntegerField(default=0)
    plan_snapshot_management_fee_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    plan_snapshot_early_withdrawal_fee_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    plan_snapshot_risk_level = models.CharField(max_length=20, blank=True, default='moderate')
    plan_snapshot_capital_protection = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.effective_plan_name}"

    def snapshot_plan_terms(self, plan: InvestmentPlan | None = None) -> None:
        plan = plan or self.plan
        if not plan:
            return
        self.plan_snapshot_name = plan.name
        self.plan_snapshot_tier = plan.plan_tier or 'standard'
        self.plan_snapshot_daily_roi = plan.effective_daily_roi
        self.plan_snapshot_total_return = plan.effective_total_return
        self.plan_snapshot_duration_days = plan.duration_days or 0
        self.plan_snapshot_payout_frequency = plan.payout_frequency or 'daily'
        self.plan_snapshot_liquidity_terms = plan.liquidity_terms or 'locked'
        self.plan_snapshot_lock_period_days = plan.lock_period_days or 0
        self.plan_snapshot_management_fee_pct = plan.management_fee_pct or Decimal('0')
        self.plan_snapshot_early_withdrawal_fee_pct = plan.early_withdrawal_fee_pct or Decimal('0')
        self.plan_snapshot_risk_level = plan.risk_level or 'moderate'
        self.plan_snapshot_capital_protection = bool(plan.capital_protection)

    @property
    def effective_plan_name(self) -> str:
        return self.plan_snapshot_name or (self.plan.name if self.plan_id else '')

    @property
    def effective_plan_tier(self) -> str:
        if self.plan_snapshot_name:
            return self.plan_snapshot_tier or 'standard'
        return self.plan.plan_tier if self.plan_id else 'standard'

    @staticmethod
    def _choice_display(choices, value: str) -> str:
        return dict(choices).get(value, value)

    @property
    def effective_daily_roi(self) -> Decimal:
        if self.plan_snapshot_name:
            return Decimal(self.plan_snapshot_daily_roi).quantize(Decimal('0.01'))
        if self.plan_id:
            return self.plan.effective_daily_roi
        return Decimal('0.00')

    @property
    def effective_total_return(self) -> Decimal:
        if self.plan_snapshot_name:
            return Decimal(self.plan_snapshot_total_return).quantize(Decimal('0.01'))
        if self.plan_id:
            return self.plan.effective_total_return
        return Decimal('0.00')

    @property
    def effective_duration_days(self) -> int:
        if self.plan_snapshot_name:
            return self.plan_snapshot_duration_days
        if self.plan_id:
            return self.plan.duration_days
        return 0

    @property
    def effective_payout_frequency(self) -> str:
        if self.plan_snapshot_name:
            return self.plan_snapshot_payout_frequency
        if self.plan_id:
            return self.plan.payout_frequency
        return 'daily'

    @property
    def effective_payout_frequency_display(self) -> str:
        return self._choice_display(InvestmentPlan.PAYOUT_CHOICES, self.effective_payout_frequency)

    @property
    def effective_liquidity_terms(self) -> str:
        if self.plan_snapshot_name:
            return self.plan_snapshot_liquidity_terms
        if self.plan_id:
            return self.plan.liquidity_terms
        return 'locked'

    @property
    def effective_liquidity_terms_display(self) -> str:
        return self._choice_display(InvestmentPlan.LIQUIDITY_CHOICES, self.effective_liquidity_terms)

    @property
    def effective_lock_period_days(self) -> int:
        if self.plan_snapshot_name:
            return self.plan_snapshot_lock_period_days
        if self.plan_id:
            return self.plan.lock_period_days
        return 0

    @property
    def effective_management_fee_pct(self) -> Decimal:
        if self.plan_snapshot_name:
            return Decimal(self.plan_snapshot_management_fee_pct).quantize(Decimal('0.01'))
        if self.plan_id:
            return self.plan.management_fee_pct or Decimal('0')
        return Decimal('0.00')

    @property
    def effective_early_withdrawal_fee_pct(self) -> Decimal:
        if self.plan_snapshot_name:
            return Decimal(self.plan_snapshot_early_withdrawal_fee_pct).quantize(Decimal('0.01'))
        if self.plan_id:
            return self.plan.early_withdrawal_fee_pct or Decimal('0')
        return Decimal('0.00')

    @property
    def effective_risk_level(self) -> str:
        if self.plan_snapshot_name:
            return self.plan_snapshot_risk_level
        if self.plan_id:
            return self.plan.risk_level
        return 'moderate'

    @property
    def effective_risk_level_display(self) -> str:
        return self._choice_display(InvestmentPlan.RISK_CHOICES, self.effective_risk_level)

    @property
    def effective_capital_protection(self) -> bool:
        return self.plan_snapshot_capital_protection if self.plan_snapshot_name else (self.plan.capital_protection if self.plan_id else True)


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
