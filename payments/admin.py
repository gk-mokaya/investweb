from django.contrib import admin

from payments.models import PaymentConfiguration, CryptoCurrency


@admin.register(PaymentConfiguration)
class PaymentConfigurationAdmin(admin.ModelAdmin):
    list_display = ('mode', 'enable_deposits', 'enable_withdrawals', 'updated_at')


@admin.register(CryptoCurrency)
class CryptoCurrencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol', 'network', 'is_active', 'created_at')
    list_filter = ('is_active', 'network')
    search_fields = ('name', 'symbol', 'network')
