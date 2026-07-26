from django.contrib import messages
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.views.generic import CreateView, ListView

from deposits.forms import DepositCreateForm
from deposits.models import Deposit
from adminpanel.utils import log_action
from accounts.services import create_notification
from investments.models import InvestmentPlan
from investments.services import create_pending_investment_request
from payments.services import get_payment_configuration
from wallets.models import Wallet


def _parse_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _safe_return_path(value):
    if not value:
        return ''
    text = str(value).strip()
    return text if text.startswith('/') else ''


def _normalize_deposit_step(value):
    return '2' if str(value).strip() == '2' else '1'


def _deposit_step_from_request(request):
    return _normalize_deposit_step(
        request.POST.get('deposit_step')
        or request.GET.get('deposit_step')
        or '1'
    )


def _investment_context_from_request(request):
    return {
        'investment_plan': request.POST.get('investment_plan') or request.GET.get('investment_plan') or '',
        'investment_amount': request.POST.get('investment_amount') or request.GET.get('investment_amount') or '',
        'investment_wallet': request.POST.get('investment_wallet') or request.GET.get('investment_wallet') or '',
    }


class DepositListView(LoginRequiredMixin, ListView):
    template_name = 'deposits_list.html'
    model = Deposit
    context_object_name = 'deposits'
    paginate_by = 10

    def get_queryset(self):
        return Deposit.objects.filter(user=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        minimum_amount = _parse_decimal(self.request.GET.get('minimum_amount'))
        return_to = _safe_return_path(self.request.GET.get('return_to'))
        source = self.request.GET.get('source', '').strip()
        deposit_step = _deposit_step_from_request(self.request)
        investment_context = _investment_context_from_request(self.request)
        context['create_form'] = DepositCreateForm(
            user=self.request.user,
            minimum_amount=minimum_amount,
            return_to=return_to,
            source=source,
            deposit_step=deposit_step,
            investment_plan=investment_context['investment_plan'],
            investment_amount=investment_context['investment_amount'],
            investment_wallet=investment_context['investment_wallet'],
        )
        context['open_deposit_modal'] = bool(self.request.GET.get('open_deposit_modal') or minimum_amount or source == 'investment' or deposit_step == '2')
        context['open_deposit_step'] = deposit_step == '2'
        context['payment_config'] = get_payment_configuration()
        context['latest_deposit'] = self.request.session.pop('latest_deposit', None)
        context['minimum_deposit_amount'] = minimum_amount
        return context


class DepositCreateView(LoginRequiredMixin, CreateView):
    template_name = 'deposits_list.html'
    form_class = DepositCreateForm
    success_url = reverse_lazy('deposit_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['minimum_amount'] = self.request.POST.get('minimum_amount') or self.request.GET.get('minimum_amount')
        kwargs['return_to'] = self.request.POST.get('return_to') or self.request.GET.get('return_to') or ''
        kwargs['source'] = self.request.POST.get('source') or self.request.GET.get('source') or ''
        kwargs['deposit_step'] = self.request.POST.get('deposit_step') or self.request.GET.get('deposit_step') or '1'
        kwargs['investment_plan'] = self.request.POST.get('investment_plan') or self.request.GET.get('investment_plan') or ''
        kwargs['investment_amount'] = self.request.POST.get('investment_amount') or self.request.GET.get('investment_amount') or ''
        kwargs['investment_wallet'] = self.request.POST.get('investment_wallet') or self.request.GET.get('investment_wallet') or ''
        return kwargs

    def form_valid(self, form):
        config = get_payment_configuration()
        if not config.enable_deposits:
            form.add_error(None, "Deposits are currently disabled.")
            return self.form_invalid(form)
        deposit = form.save(commit=False)
        deposit.user = self.request.user
        deposit.wallet = form.cleaned_data.get('wallet')
        if not deposit.wallet:
            form.add_error('wallet', "Please choose a wallet.")
            return self.form_invalid(form)
        deposit.method = 'manual'
        deposit.status = 'pending'
        if deposit.wallet.user_id != self.request.user.id:
            form.add_error('wallet', "Invalid wallet selection.")
            return self.form_invalid(form)

        if not deposit.sender_address:
            form.add_error('sender_address', "Sender address is required for manual deposits.")
        if form.errors:
            return self.form_invalid(form)

        pending_investment = None
        source = (form.cleaned_data.get('source') or '').strip()
        with transaction.atomic():
            if source == 'investment':
                investment_plan_id = form.cleaned_data.get('investment_plan') or form.data.get('investment_plan')
                investment_amount = form.cleaned_data.get('investment_amount') or form.data.get('investment_amount')
                investment_wallet_id = form.cleaned_data.get('investment_wallet') or form.data.get('investment_wallet')
                if not investment_plan_id or investment_amount in (None, ''):
                    form.add_error(None, "Your investment details are missing. Please restart the investment flow.")
                    return self.form_invalid(form)
                try:
                    investment_amount = Decimal(str(investment_amount))
                except (TypeError, ValueError, InvalidOperation):
                    form.add_error(None, "Your investment details are invalid. Please restart the investment flow.")
                    return self.form_invalid(form)

                investment_plan = get_object_or_404(InvestmentPlan, pk=investment_plan_id, is_active=True)
                investment_wallet = deposit.wallet
                if investment_wallet_id:
                    investment_wallet = get_object_or_404(
                        Wallet,
                        pk=investment_wallet_id,
                        user=self.request.user,
                        wallet_type='primary',
                        is_active=True,
                    )
                if investment_amount < investment_plan.min_amount:
                    form.add_error(None, f"Investment amount must be at least {investment_plan.min_amount}.")
                    return self.form_invalid(form)
                if investment_plan.max_amount and investment_amount > investment_plan.max_amount:
                    form.add_error(None, f"Investment amount must be at most {investment_plan.max_amount}.")
                    return self.form_invalid(form)

                pending_investment = create_pending_investment_request(
                    self.request.user,
                    investment_plan,
                    investment_amount,
                    wallet=investment_wallet,
                )
                deposit.investment_request = pending_investment

            deposit.save()
        log_action(self.request.user, 'deposit_created', 'deposit', deposit.id, {'crypto': deposit.crypto.symbol})
        messages.success(self.request, "Deposit submitted. Our team will review it shortly.")
        if pending_investment:
            create_notification(
                self.request.user,
                "Investment request received",
                f"Your {pending_investment.effective_plan_name} investment request for {pending_investment.amount} has been created and will activate after the deposit is verified.",
                level='info',
            )
        create_notification(
            self.request.user,
            "Deposit submitted",
            f"Your {deposit.crypto.symbol} deposit of {deposit.amount} has been received and is pending admin approval. Once verified, it will activate your linked investment request.",
            level='info',
        )
        self.request.session['latest_deposit'] = {
            'id': deposit.id,
            'crypto': deposit.crypto.symbol,
            'network': deposit.crypto.network,
            'amount': str(deposit.amount),
        }
        self.object = deposit
        if form.cleaned_data.get('source') == 'investment':
            return redirect(self.get_success_url())
        return_to = _safe_return_path(form.cleaned_data.get('return_to'))
        return redirect(return_to or self.get_success_url())

    def form_invalid(self, form):
        deposits = Deposit.objects.filter(user=self.request.user).order_by('-created_at')
        context = self.get_context_data(form=form)
        context['deposits'] = deposits
        context['create_form'] = form
        context['open_deposit_modal'] = True
        context['open_deposit_step'] = _normalize_deposit_step(form.data.get('deposit_step')) == '2'
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deposits'] = Deposit.objects.filter(user=self.request.user).order_by('-created_at')
        create_form = context.get(
            'form',
            DepositCreateForm(
                user=self.request.user,
                minimum_amount=_parse_decimal(self.request.GET.get('minimum_amount')),
                return_to=_safe_return_path(self.request.GET.get('return_to')),
                source=self.request.GET.get('source', '').strip(),
                deposit_step=_normalize_deposit_step(self.request.GET.get('deposit_step')),
            ),
        )
        context['create_form'] = create_form
        current_step = _deposit_step_from_request(self.request)
        context['open_deposit_modal'] = bool(self.request.GET.get('open_deposit_modal') or self.request.GET.get('minimum_amount') or self.request.GET.get('source') == 'investment' or current_step == '2')
        context['open_deposit_step'] = current_step == '2'
        context['payment_config'] = get_payment_configuration()
        context['latest_deposit'] = self.request.session.pop('latest_deposit', None)
        context['minimum_deposit_amount'] = getattr(create_form, 'minimum_amount', None) or _parse_decimal(self.request.GET.get('minimum_amount'))
        return context

# Create your views here.
