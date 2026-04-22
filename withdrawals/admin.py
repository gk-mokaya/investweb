from django.contrib import admin
from withdrawals.models import Withdrawal


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'crypto', 'method', 'amount', 'destination_network', 'status', 'created_at', 'processed_at')
    list_filter = ('status', 'method', 'crypto')
    search_fields = ('user__username', 'user__email')

# Register your models here.
