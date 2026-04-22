from django.contrib import admin
from deposits.models import Deposit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'crypto', 'method', 'amount', 'status', 'provider', 'created_at', 'completed_at')
    list_filter = ('status', 'method', 'crypto')
    search_fields = ('user__username', 'user__email')

# Register your models here.
