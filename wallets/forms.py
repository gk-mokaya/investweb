from django import forms

from wallets.models import Wallet


class WalletCreateForm(forms.ModelForm):
    class Meta:
        model = Wallet
        fields = ('name', 'wallet_type')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        self.fields['name'].widget.attrs.update({'placeholder': 'e.g. Trading Wallet'})
        self.fields['wallet_type'].required = True
        self.fields['wallet_type'].choices = [
            ('trading', 'Trading'),
            ('savings', 'Savings'),
        ]

    def clean_wallet_type(self):
        value = self.cleaned_data.get('wallet_type')
        if value == 'primary':
            raise forms.ValidationError("You cannot create a primary wallet.")
        if value not in {'trading', 'savings'}:
            raise forms.ValidationError("Select a valid wallet type.")
        return value


class WalletTransferForm(forms.Form):
    from_wallet = forms.ModelChoiceField(queryset=Wallet.objects.none())
    to_wallet = forms.ModelChoiceField(queryset=Wallet.objects.none())
    amount = forms.DecimalField(min_value=1, decimal_places=2, max_digits=12)
    note = forms.CharField(required=False, max_length=200)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            qs = Wallet.objects.filter(user=user, is_active=True).order_by('-is_default', 'created_at')
            self.fields['from_wallet'].queryset = qs
            self.fields['to_wallet'].queryset = qs
            self.fields['from_wallet'].empty_label = 'Select source wallet'
            self.fields['to_wallet'].empty_label = 'Select destination wallet'
