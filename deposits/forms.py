from django import forms

from deposits.models import Deposit
from wallets.models import Wallet
from payments.services import get_payment_configuration, get_active_cryptos


class DepositCreateForm(forms.ModelForm):
    class Meta:
        model = Deposit
        fields = (
            'wallet',
            'crypto',
            'method',
            'amount',
            'transaction_hash',
            'sender_address',
        )

    def __init__(self, *args, user=None, **kwargs):
        import json
        super().__init__(*args, **kwargs)
        config = get_payment_configuration()
        if user:
            wallets = Wallet.objects.filter(user=user, is_active=True).order_by('-is_default', 'created_at')
            self.fields['wallet'].queryset = wallets
            self.fields['wallet'].empty_label = 'Select wallet'
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            balances = {str(w.id): str(w.total_balance) for w in wallets}
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps(balances),
                'data-balance-target': 'depositWalletBalance',
            })
        self.fields['crypto'].queryset = get_active_cryptos()
        self.fields['crypto'].empty_label = 'Select crypto'
        self.fields['method'].help_text = 'Manual requires TXID + sender address. Automated generates a pay address.'
        self.fields['amount'].widget.attrs.update({
            'min': '0.01',
            'step': '0.01',
        })
        self.fields['transaction_hash'].widget.attrs.update({
            'placeholder': 'Paste transaction hash after sending',
            'data-method-only': 'manual',
            'data-method-required': 'manual',
            'data_required_hint': 'manual',
        })
        self.fields['sender_address'].required = False
        self.fields['sender_address'].widget.attrs.update({
            'placeholder': 'Sender wallet address',
            'data-method-only': 'manual',
            'data-method-required': 'manual',
        })
        if config.mode == 'hybrid':
            self.fields['method'].required = True
            choices = list(self.fields['method'].choices)
            if not choices or choices[0][0] != '':
                self.fields['method'].choices = [('', 'Select method')] + choices
        else:
            self.fields['method'].required = False
            self.fields['method'].widget = forms.HiddenInput()
            self.fields['method'].initial = config.mode

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get('method') or self.fields['method'].initial
        tx_hash = cleaned_data.get('transaction_hash')
        if method == 'manual' and not tx_hash:
            self.add_error('transaction_hash', 'Transaction hash is required for manual deposits.')
        return cleaned_data
