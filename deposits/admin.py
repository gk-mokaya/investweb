from django.contrib import admin
from deposits.models import Deposit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'crypto',
        'method',
        'amount',
        'status',
        'reviewed_by',
        'reviewed_at',
        'created_at',
        'completed_at',
    )
    list_filter = ('status', 'method', 'crypto')
    search_fields = ('user__username', 'user__email', 'transaction_hash', 'sender_address', 'review_note')

# Register your models here.
