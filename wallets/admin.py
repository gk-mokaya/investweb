from django.contrib import admin
from wallets.models import Wallet, Transaction, WalletTransfer


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'wallet_type', 'is_default', 'is_active', 'main_balance', 'bonus_balance', 'profit_balance', 'created_at')
    search_fields = ('user__username', 'user__email', 'name')
    list_filter = ('wallet_type', 'is_default', 'is_active')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'txn_type', 'amount', 'balance_after', 'created_at')
    list_filter = ('txn_type',)
    search_fields = ('user__username', 'user__email')


@admin.register(WalletTransfer)
class WalletTransferAdmin(admin.ModelAdmin):
    list_display = ('user', 'from_wallet', 'to_wallet', 'amount', 'bucket', 'status', 'created_at')
    list_filter = ('status', 'bucket')
    search_fields = ('user__username', 'from_wallet__name', 'to_wallet__name')

# Register your models here.
