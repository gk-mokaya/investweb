from django.contrib import admin
from investments.models import BonusTracker, DailyProfit, InvestmentPlan, UserInvestment


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_amount', 'max_amount', 'daily_roi', 'duration_days', 'total_return', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'start_date', 'end_date', 'total_earned', 'is_completed')
    list_filter = ('is_completed',)
    search_fields = ('user__username', 'plan__name')


@admin.register(DailyProfit)
class DailyProfitAdmin(admin.ModelAdmin):
    list_display = ('investment', 'date', 'amount', 'created_at')
    list_filter = ('date',)


@admin.register(BonusTracker)
class BonusTrackerAdmin(admin.ModelAdmin):
    list_display = ('user', 'bonus_amount', 'required_profit', 'achieved_profit', 'is_unlocked')
    search_fields = ('user__username',)

# Register your models here.
