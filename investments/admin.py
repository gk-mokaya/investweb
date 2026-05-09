from django.contrib import admin
from investments.models import DailyProfit, InvestmentAccount, InvestmentPlan, UserInvestment


@admin.register(InvestmentAccount)
class InvestmentAccountAdmin(admin.ModelAdmin):
    list_display = ('ledger_code', 'user', 'active_positions_count', 'completed_positions_count', 'current_balance', 'total_earned', 'created_at')
    search_fields = ('ledger_code', 'user__username', 'user__email')
    readonly_fields = ('active_positions_count', 'completed_positions_count', 'current_balance', 'total_earned')


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'version_number', 'source_plan', 'min_amount', 'max_amount', 'total_return', 'daily_roi', 'duration_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'source_plan__name')


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'account',
        'effective_plan_name',
        'amount',
        'plan_snapshot_total_return',
        'plan_snapshot_payout_frequency',
        'start_date',
        'end_date',
        'total_earned',
        'is_completed',
    )
    list_filter = ('is_completed', 'plan_snapshot_payout_frequency')
    search_fields = ('user__username', 'plan__name', 'plan_snapshot_name', 'account__user__username')
    readonly_fields = (
        'plan_snapshot_name',
        'plan_snapshot_tier',
        'plan_snapshot_daily_roi',
        'plan_snapshot_total_return',
        'plan_snapshot_duration_days',
        'plan_snapshot_payout_frequency',
        'plan_snapshot_liquidity_terms',
        'plan_snapshot_lock_period_days',
        'plan_snapshot_management_fee_pct',
        'plan_snapshot_early_withdrawal_fee_pct',
        'plan_snapshot_risk_level',
        'plan_snapshot_capital_protection',
        'settled_at',
    )


@admin.register(DailyProfit)
class DailyProfitAdmin(admin.ModelAdmin):
    list_display = ('investment', 'date', 'amount', 'created_at')
    list_filter = ('date',)

# Register your models here.
