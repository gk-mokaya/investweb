from django import forms

from deposits.models import Deposit
from wallets.models import Wallet
from payments.services import get_active_cryptos


class DepositCreateForm(forms.ModelForm):
    class Meta:
        model = Deposit
        fields = (
            'wallet',
            'crypto',
            'amount',
            'transaction_hash',
            'sender_address',
        )

    def __init__(self, *args, user=None, **kwargs):
        import json
        super().__init__(*args, **kwargs)
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
        self.fields['crypto'].queryset = get_active_cryptos().filter(symbol='USDT', network='TRC20')
        self.fields['crypto'].empty_label = 'USDT (TRC20)'
        self.fields['crypto'].help_text = 'Manual deposits are accepted only for USDT on the TRC20 network.'
        self.fields['amount'].widget.attrs.update({
            'min': '0.01',
            'step': '0.01',
        })
        self.fields['transaction_hash'].widget.attrs.update({
            'placeholder': 'Paste transaction hash after sending',
        })
        self.fields['sender_address'].required = True
        self.fields['sender_address'].widget.attrs.update({
            'placeholder': 'Sender wallet address',
        })
        self.fields['transaction_hash'].required = True
        self.fields['transaction_hash'].help_text = 'Submit the TXID/transaction hash after sending the funds.'
        self.fields['sender_address'].help_text = 'Paste the wallet address you sent the deposit from.'
