from django import forms

from withdrawals.models import Withdrawal
from wallets.models import Wallet
from payments.services import get_payment_configuration, get_active_cryptos


class WithdrawalCreateForm(forms.ModelForm):
    class Meta:
        model = Withdrawal
        fields = (
            'wallet',
            'amount',
            'crypto',
            'wallet_address',
            'destination_network',
            'memo_tag',
            'method',
        )

    def __init__(self, *args, user=None, **kwargs):
        import json
        super().__init__(*args, **kwargs)
        config = get_payment_configuration()
        trc20_crypto = get_active_cryptos().filter(symbol='USDT', network='TRC20').first()
        if user:
            wallets = Wallet.objects.filter(user=user, wallet_type='primary', is_active=True).order_by('-is_default', 'created_at')
            self.fields['wallet'].queryset = wallets
            self.fields['wallet'].empty_label = 'Select wallet'
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            balances = {str(w.id): str(w.total_balance) for w in wallets}
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps(balances),
                'data-balance-target': 'withdrawalWalletBalance',
                'data-autofill-target': 'id_amount',
            })
        self.fields['crypto'].queryset = get_active_cryptos().filter(symbol='USDT', network='TRC20')
        self.fields['crypto'].empty_label = 'Select crypto'
        if trc20_crypto:
            self.fields['crypto'].initial = trc20_crypto.pk
        self.fields['crypto'].help_text = 'TRC20 is the current network, selected automatically.'
        self.fields['amount'].widget.attrs.update({
            'min': '0.01',
            'step': '0.01',
        })
        self.fields['wallet_address'].widget.attrs.update({
            'placeholder': 'Payout wallet address',
        })
        self.fields['wallet_address'].help_text = 'Paste the address where you want the withdrawal sent.'
        self.fields['destination_network'].widget = forms.HiddenInput()
        self.fields['memo_tag'].widget = forms.HiddenInput()
        self.fields['method'].widget = forms.HiddenInput()
        self.fields['method'].initial = config.mode if config.mode != 'hybrid' else 'manual'
