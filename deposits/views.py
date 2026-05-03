from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.views.generic import CreateView, ListView

from deposits.forms import DepositCreateForm
from deposits.models import Deposit
from adminpanel.utils import log_action
from accounts.services import create_notification
from payments.services import get_payment_configuration


class DepositListView(LoginRequiredMixin, ListView):
    template_name = 'deposits_list.html'
    model = Deposit
    context_object_name = 'deposits'
    paginate_by = 10

    def get_queryset(self):
        return Deposit.objects.filter(user=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = DepositCreateForm(user=self.request.user)
        context['open_deposit_modal'] = False
        context['payment_config'] = get_payment_configuration()
        context['latest_deposit'] = self.request.session.pop('latest_deposit', None)
        return context


class DepositCreateView(LoginRequiredMixin, CreateView):
    template_name = 'deposits_list.html'
    form_class = DepositCreateForm
    success_url = reverse_lazy('deposit_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        config = get_payment_configuration()
        if not config.enable_deposits:
            form.add_error(None, "Deposits are currently disabled.")
            return self.form_invalid(form)
        deposit = form.save(commit=False)
        deposit.user = self.request.user
        deposit.wallet = form.cleaned_data.get('wallet')
        deposit.method = 'manual'
        deposit.status = 'pending'
        if deposit.wallet and deposit.wallet.user_id != self.request.user.id:
            form.add_error('wallet', "Invalid wallet selection.")
            return self.form_invalid(form)

        if not deposit.transaction_hash:
            form.add_error('transaction_hash', "Transaction hash is required for manual deposits.")
        if not deposit.sender_address:
            form.add_error('sender_address', "Sender address is required for manual deposits.")
        if form.errors:
            return self.form_invalid(form)

        deposit.save()
        log_action(self.request.user, 'deposit_created', 'deposit', deposit.id, {'crypto': deposit.crypto.symbol})
        messages.success(self.request, "Deposit submitted. Our team will review it shortly.")
        create_notification(
            self.request.user,
            "Deposit submitted",
            f"Your {deposit.crypto.symbol} deposit of {deposit.amount} is pending manual review.",
            level='info',
        )
        self.request.session['latest_deposit'] = {
            'id': deposit.id,
            'crypto': deposit.crypto.symbol,
            'network': deposit.crypto.network,
            'amount': str(deposit.amount),
        }
        self.object = deposit
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        deposits = Deposit.objects.filter(user=self.request.user).order_by('-created_at')
        context = self.get_context_data(form=form)
        context['deposits'] = deposits
        context['create_form'] = form
        context['open_deposit_modal'] = True
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deposits'] = Deposit.objects.filter(user=self.request.user).order_by('-created_at')
        context['create_form'] = context.get('form', DepositCreateForm(user=self.request.user))
        context['open_deposit_modal'] = False
        context['payment_config'] = get_payment_configuration()
        context['latest_deposit'] = self.request.session.pop('latest_deposit', None)
        return context

# Create your views here.
