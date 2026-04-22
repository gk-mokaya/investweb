from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from investments.services import can_withdraw
from wallets.services import debit_wallet
from withdrawals.forms import WithdrawalCreateForm
from withdrawals.models import Withdrawal
from adminpanel.utils import log_action
from accounts.services import create_notification
from kyc.models import KYCProfile
from payments.services import get_payment_configuration


class WithdrawalListView(LoginRequiredMixin, ListView):
    template_name = 'withdrawals_list.html'
    model = Withdrawal
    context_object_name = 'withdrawals'
    paginate_by = 10

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = WithdrawalCreateForm(user=self.request.user)
        context['open_withdrawal_modal'] = False
        context['payment_config'] = get_payment_configuration()
        kyc_profile = KYCProfile.objects.filter(user=self.request.user).first()
        context['kyc_verified'] = bool(kyc_profile and kyc_profile.status == 'verified')
        context['kyc_status'] = kyc_profile.status if kyc_profile else None
        return context


class WithdrawalCreateView(LoginRequiredMixin, CreateView):
    template_name = 'withdrawals_list.html'
    form_class = WithdrawalCreateForm
    success_url = reverse_lazy('withdrawal_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        amount = form.cleaned_data['amount']
        config = get_payment_configuration()
        if not config.enable_withdrawals:
            form.add_error(None, "Withdrawals are currently disabled.")
            return self.form_invalid(form)
        kyc_profile = KYCProfile.objects.filter(user=self.request.user).first()
        if not kyc_profile or kyc_profile.status != 'verified':
            form.add_error(None, "KYC verification is required before withdrawals.")
            return self.form_invalid(form)

        allowed, reason = can_withdraw(self.request.user, amount)
        if not allowed:
            form.add_error(None, reason)
            return self.form_invalid(form)

        wallet = form.cleaned_data.get('wallet')
        if wallet and wallet.user_id != self.request.user.id:
            form.add_error('wallet', "Invalid wallet selection.")
            return self.form_invalid(form)
        if amount > wallet.profit_balance:
            form.add_error('amount', "Insufficient profit balance.")
            return self.form_invalid(form)

        withdrawal = form.save(commit=False)
        withdrawal.user = self.request.user
        withdrawal.wallet = wallet
        if config.mode == 'manual':
            withdrawal.method = 'manual'
        elif config.mode == 'automated':
            withdrawal.method = 'automated'
        else:
            withdrawal.method = form.cleaned_data.get('method') or 'manual'
        withdrawal.status = 'pending'
        withdrawal.save()
        log_action(self.request.user, 'withdrawal_created', 'withdrawal', withdrawal.id, {'amount': str(amount)})

        debit_wallet(wallet, amount, 'profit', 'withdrawal', {'withdrawal_id': withdrawal.id})
        messages.success(self.request, "Withdrawal request created.")
        create_notification(
            self.request.user,
            "Withdrawal requested",
            f"Your withdrawal of {amount} is {withdrawal.get_status_display().lower()}.",
            level='info',
        )
        self.object = withdrawal
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        withdrawals = Withdrawal.objects.filter(user=self.request.user).order_by('-created_at')
        context = self.get_context_data(form=form)
        context['withdrawals'] = withdrawals
        context['create_form'] = form
        context['open_withdrawal_modal'] = True
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['withdrawals'] = Withdrawal.objects.filter(user=self.request.user).order_by('-created_at')
        context['create_form'] = context.get('form', WithdrawalCreateForm(user=self.request.user))
        context['open_withdrawal_modal'] = False
        context['payment_config'] = get_payment_configuration()
        kyc_profile = KYCProfile.objects.filter(user=self.request.user).first()
        context['kyc_verified'] = bool(kyc_profile and kyc_profile.status == 'verified')
        context['kyc_status'] = kyc_profile.status if kyc_profile else None
        return context

# Create your views here.
