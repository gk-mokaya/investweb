from django import forms
import json

from investments.models import InvestmentPlan
from wallets.models import Wallet


class CreateInvestmentForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=InvestmentPlan.objects.none())
    wallet = forms.ModelChoiceField(queryset=Wallet.objects.none())
    amount = forms.DecimalField(min_value=1, decimal_places=2, max_digits=12)
    risk_acknowledged = forms.BooleanField(required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        plans = InvestmentPlan.objects.filter(is_active=True)
        self.fields['plan'].queryset = plans
        self.fields['plan'].empty_label = 'Select plan'
        plan_meta = {}
        for plan in plans:
            plan_meta[str(plan.id)] = {
                'name': plan.name,
                'min_amount': str(plan.min_amount),
                'max_amount': str(plan.max_amount) if plan.max_amount else '',
                'daily_roi': str(plan.daily_roi),
                'duration_days': plan.duration_days,
                'total_return': str(plan.total_return),
                'payout_frequency': plan.payout_frequency,
                'liquidity_terms': plan.liquidity_terms,
                'lock_period_days': plan.lock_period_days,
                'risk_level': plan.risk_level,
                'management_fee_pct': str(plan.management_fee_pct),
                'early_withdrawal_fee_pct': str(plan.early_withdrawal_fee_pct),
                'capital_protection': bool(plan.capital_protection),
            }
        self.fields['plan'].widget.attrs.update({
            'data-plan-meta': json.dumps(plan_meta),
        })
        if user:
            wallets = Wallet.objects.filter(
                user=user,
                wallet_type__in=['primary', 'trading'],
                is_active=True,
            ).order_by('-is_default', 'created_at')
            self.fields['wallet'].queryset = wallets
            self.fields['wallet'].empty_label = 'Select wallet'
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            balances = {str(w.id): str(w.total_balance) for w in wallets}
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps(balances),
                'data-balance-target': 'investmentWalletBalance',
            })
        self.fields['amount'].widget.attrs.update({
            'placeholder': 'Enter amount',
            'min': '1',
            'step': '0.01',
            'inputmode': 'decimal',
        })


class InvestmentPlanForm(forms.ModelForm):
    class Meta:
        model = InvestmentPlan
        fields = (
            'name',
            'plan_tier',
            'min_amount',
            'max_amount',
            'daily_roi',
            'duration_days',
            'description',
            'risk_level',
            'payout_frequency',
            'liquidity_terms',
            'lock_period_days',
            'management_fee_pct',
            'capital_protection',
            'early_withdrawal_fee_pct',
            'is_active',
        )
