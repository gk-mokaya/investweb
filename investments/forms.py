from django import forms
import json
from decimal import Decimal

from django import forms

from investments.models import InvestmentPlan
from wallets.models import Wallet


class CreateInvestmentForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=InvestmentPlan.objects.none())
    amount = forms.DecimalField(min_value=1, decimal_places=2, max_digits=12)
    wallet = forms.ModelChoiceField(queryset=Wallet.objects.none())

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
                'daily_roi': str(plan.effective_daily_roi),
                'total_return': str(plan.effective_total_return),
                'duration_days': plan.duration_days,
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
                wallet_type='primary',
                is_active=True,
            ).order_by('-is_default', 'created_at')
            self.fields['wallet'].queryset = wallets
            self.fields['wallet'].empty_label = 'Select wallet'
            self.fields['wallet'].label = 'Funding Wallet'
            self.fields['wallet'].label_from_instance = lambda obj: f"{obj.name} - {obj.get_wallet_type_display()}"
            balances = {str(w.id): str(w.total_balance) for w in wallets}
            self.fields['wallet'].widget.attrs.update({
                'data-wallet-balances': json.dumps(balances),
                'data-balance-target': 'investmentWalletBalance',
            })
        self.fields['amount'].label = 'Amount to invest'
        self.fields['amount'].help_text = 'Enter the amount first so we can validate it against the selected plan.'
        self.fields['amount'].widget.attrs.update({
            'placeholder': 'Enter amount',
            'min': '1',
            'step': '0.01',
            'inputmode': 'decimal',
        })
        self.fields['wallet'].label = 'Funding Wallet'
        self.fields['wallet'].help_text = 'Select the funding wallet after choosing your amount.'

    def clean(self):
        cleaned_data = super().clean()
        plan = cleaned_data.get('plan')
        amount = cleaned_data.get('amount')
        if plan and amount is not None:
            if amount < plan.min_amount:
                self.add_error('amount', f"Amount must be at least {plan.min_amount}.")
            elif plan.max_amount and amount > plan.max_amount:
                self.add_error('amount', f"Amount must be at most {plan.max_amount}.")
        return cleaned_data


class InvestmentPlanForm(forms.ModelForm):
    class Meta:
        model = InvestmentPlan
        fields = (
            'name',
            'plan_tier',
            'min_amount',
            'max_amount',
            'total_return',
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
        labels = {
            'total_return': 'Total Profit (%)',
            'min_amount': 'Minimum Amount',
            'max_amount': 'Maximum Amount',
            'management_fee_pct': 'Management Fee (%)',
            'early_withdrawal_fee_pct': 'Early Withdrawal Fee (%)',
        }
        help_texts = {
            'total_return': 'Enter the total profit percentage for the full investment period.',
            'min_amount': 'Currency amount required to start this plan.',
            'max_amount': 'Currency cap for this plan, if any.',
            'management_fee_pct': 'Percentage deducted from each profit payout.',
            'early_withdrawal_fee_pct': 'Percentage charged only if the user exits early.',
        }
