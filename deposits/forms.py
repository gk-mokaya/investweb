from django import forms
from decimal import Decimal, InvalidOperation

from django import forms

from deposits.models import Deposit
from wallets.models import Wallet
from wallets.services import get_primary_wallet
from payments.services import get_active_cryptos


class DepositCreateForm(forms.ModelForm):
    minimum_amount = forms.DecimalField(required=False, widget=forms.HiddenInput())
    return_to = forms.CharField(required=False, widget=forms.HiddenInput())
    source = forms.CharField(required=False, widget=forms.HiddenInput())
    deposit_step = forms.CharField(required=False, widget=forms.HiddenInput())
    investment_plan = forms.CharField(required=False, widget=forms.HiddenInput())
    investment_amount = forms.DecimalField(required=False, widget=forms.HiddenInput())
    investment_wallet = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Deposit
        fields = (
            'wallet',
            'crypto',
            'amount',
            'sender_address',
            'screenshot',
        )

    def __init__(
        self,
        *args,
        user=None,
        minimum_amount=None,
        return_to='',
        source='',
        deposit_step='1',
        investment_plan='',
        investment_amount='',
        investment_wallet='',
        **kwargs,
    ):
        import json
        super().__init__(*args, **kwargs)
        self.minimum_amount = None
        try:
            if minimum_amount not in (None, ''):
                self.minimum_amount = Decimal(str(minimum_amount))
        except (TypeError, ValueError, InvalidOperation):
            self.minimum_amount = None
        if self.minimum_amount is not None:
            self.fields['minimum_amount'].initial = self.minimum_amount
        if return_to:
            self.fields['return_to'].initial = return_to
        if source:
            self.fields['source'].initial = source
        self.fields['deposit_step'].initial = deposit_step or '1'
        if investment_plan:
            self.fields['investment_plan'].initial = str(investment_plan)
        if investment_amount not in (None, ''):
            self.fields['investment_amount'].initial = str(investment_amount)
        if investment_wallet:
            self.fields['investment_wallet'].initial = str(investment_wallet)
        primary_wallet = get_primary_wallet(user) if user else None
        trc20_crypto = get_active_cryptos().filter(symbol='USDT', network='TRC20').first()
        if primary_wallet:
            self.fields['wallet'].queryset = Wallet.objects.filter(pk=primary_wallet.pk)
            self.fields['wallet'].initial = primary_wallet.pk
            self.fields['wallet'].disabled = True
            self.fields['wallet'].empty_label = None
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps({str(primary_wallet.id): str(primary_wallet.total_balance)}),
                'data-balance-target': 'depositWalletBalance',
            })
        else:
            self.fields['wallet'].queryset = Wallet.objects.none()
            self.fields['wallet'].disabled = True
            self.fields['wallet'].empty_label = 'Primary wallet unavailable'

        self.fields['wallet'].help_text = ''
        self.fields['wallet'].label = 'Wallet'

        self.fields['crypto'].queryset = get_active_cryptos().filter(symbol='USDT', network='TRC20')
        self.fields['crypto'].empty_label = None
        self.fields['crypto'].disabled = True
        if trc20_crypto:
            self.fields['crypto'].initial = trc20_crypto.pk
        self.fields['crypto'].label = 'Crypto'
        self.fields['crypto'].help_text = ''
        self.fields['amount'].widget.attrs.update({
            'min': '0.01',
            'step': '0.01',
        })
        self.fields['amount'].label = 'Amount withdrawn'
        self.fields['amount'].help_text = ''
        self.fields['sender_address'].required = True
        self.fields['sender_address'].widget.attrs.update({
            'placeholder': 'Sender email or Binance ID',
        })
        self.fields['sender_address'].label = 'Sender email or Binance ID'
        self.fields['sender_address'].help_text = ''
        self.fields['screenshot'].required = True
        self.fields['screenshot'].widget.attrs.update({
            'accept': 'image/*',
        })
        self.fields['screenshot'].label = 'Transaction screenshot'
        self.fields['screenshot'].help_text = ''
        if self.minimum_amount is not None:
            self.fields['amount'].help_text = ''

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and self.minimum_amount is not None and amount < self.minimum_amount:
            raise forms.ValidationError(f"Deposit amount must be at least {self.minimum_amount}.")
        return amount
