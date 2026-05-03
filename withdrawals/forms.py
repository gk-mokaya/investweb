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
        if user:
            wallets = Wallet.objects.filter(user=user, is_active=True).order_by('-is_default', 'created_at')
            self.fields['wallet'].queryset = wallets
            self.fields['wallet'].empty_label = 'Select wallet'
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            balances = {str(w.id): str(w.total_balance) for w in wallets}
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps(balances),
                'data-balance-target': 'withdrawalWalletBalance',
                'data-autofill-target': 'id_amount',
            })
        self.fields['crypto'].queryset = get_active_cryptos()
        self.fields['crypto'].empty_label = 'Select crypto'
        self.fields['method'].help_text = 'Manual is processed by admin. Automated sends after approval.'
        self.fields['amount'].widget.attrs.update({
            'min': '0.01',
            'step': '0.01',
        })
        self.fields['wallet_address'].widget.attrs.update({
            'placeholder': 'Recipient wallet address',
        })
        self.fields['destination_network'].help_text = 'Optional: specify a network if the receiving wallet requires it.'
        self.fields['destination_network'].widget.attrs.update({
            'placeholder': 'Optional network (e.g., TRC20)',
        })
        self.fields['memo_tag'].help_text = 'Optional: include a memo/tag if required by the destination.'
        self.fields['memo_tag'].widget.attrs.update({
            'placeholder': 'Optional memo/tag',
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
