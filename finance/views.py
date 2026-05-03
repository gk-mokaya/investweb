from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from adminpanel.utils import log_action
from deposits.models import Deposit
from deposits.services import verify_and_update_deposit, ProviderError
from investments.forms import InvestmentPlanForm
from investments.models import InvestmentPlan
from payments.models import CryptoCurrency, PaymentConfiguration
from payments.services import get_payment_configuration
from wallets.models import Wallet
from wallets.services import credit_wallet
from withdrawals.models import Withdrawal
from withdrawals.services import process_automated_withdrawal, mark_withdrawal_completed
from settingsconfig.models import SystemSetting
from settingsconfig.utils import DEFAULT_SETTINGS, get_setting


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


def build_plan_page_context(request, *, plans=None, create_form=None, edit_form=None, edit_plan_id=None, open_create_modal=False):
    plans = plans if plans is not None else _filter_plans_for_request(request)
    return {
        'plans': plans,
        'create_form': create_form or InvestmentPlanForm(),
        'open_create_modal': open_create_modal,
        'edit_plan_id': edit_plan_id,
        'edit_form': edit_form,
        'plan_forms': [(plan, InvestmentPlanForm(instance=plan)) for plan in plans],
        'plan_tier_choices': InvestmentPlan.TIER_CHOICES,
        'status_choices': [('', 'All statuses'), ('active', 'Active'), ('inactive', 'Paused')],
    }


def _filter_plans_for_request(request):
    queryset = InvestmentPlan.objects.all().order_by('min_amount')
    query = request.GET.get('q', '').strip()
    tier = request.GET.get('tier', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if tier:
        queryset = queryset.filter(plan_tier=tier)
    if status == 'active':
        queryset = queryset.filter(is_active=True)
    elif status == 'inactive':
        queryset = queryset.filter(is_active=False)
    return queryset


class AdminPlanListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'admin_plans.html'
    model = InvestmentPlan
    context_object_name = 'plans'
    paginate_by = 20

    def get_queryset(self):
        return _filter_plans_for_request(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_plan_page_context(self.request, plans=context['plans']))
        return context


class DepositQueueView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'pending_deposits.html'
    model = Deposit
    context_object_name = 'deposits'
    paginate_by = 25

    def get_queryset(self):
        queryset = Deposit.objects.select_related('user', 'wallet', 'crypto', 'reviewed_by').order_by('-created_at')
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()
        crypto = self.request.GET.get('crypto', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        if crypto:
            queryset = queryset.filter(crypto_id=crypto)
        if query:
            queryset = queryset.filter(
                Q(user__username__icontains=query)
                | Q(transaction_hash__icontains=query)
                | Q(sender_address__icontains=query)
                | Q(review_note__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Deposit.STATUS_CHOICES
        context['crypto_choices'] = CryptoCurrency.objects.filter(is_active=True).order_by('symbol', 'network')
        return context


class WithdrawalQueueView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'pending_withdrawals.html'
    model = Withdrawal
    context_object_name = 'withdrawals'
    paginate_by = 25

    def get_queryset(self):
        queryset = Withdrawal.objects.select_related('user', 'wallet', 'crypto').order_by('-created_at')
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(wallet_address__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Withdrawal.STATUS_CHOICES
        return context


class WalletQueueView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'admin_wallets.html'
    model = Wallet
    context_object_name = 'wallets'
    paginate_by = 25

    def get_queryset(self):
        queryset = Wallet.objects.select_related('user').order_by('-created_at')
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(name__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = [('active', 'Active'), ('inactive', 'Inactive')]
        return context


class SiteSettingsPageView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'admin_site_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_keys = [
            'PROJECT_NAME',
            'SITE_TAGLINE',
            'SUPPORT_EMAIL',
            'SUPPORT_PHONE',
            'SUPPORT_ADDRESS',
            'CURRENCY',
            'WELCOME_BONUS',
            'MIN_WITHDRAWAL_AMOUNT',
            'CRYPTO_PROVIDER',
            'BLOCKCYPHER_TOKEN',
            'BLOCKCYPHER_CALLBACK_URL',
            'DESTINATION_BTC_ADDRESS',
            'DESTINATION_ETH_ADDRESS',
            'DESTINATION_USDT_ADDRESS',
            'GMAIL_CLIENT_ID',
            'GMAIL_CLIENT_SECRET',
            'GMAIL_REFRESH_TOKEN',
            'GMAIL_SENDER_EMAIL',
            'MANUAL_DEPOSIT_WALLET_ADDRESS',
        ]
        context['site_settings'] = {key: get_setting(key, default=DEFAULT_SETTINGS.get(key, '')) for key in site_keys}
        context['payment_config'] = PaymentConfiguration.objects.first()
        context['payment_mode_choices'] = PaymentConfiguration.MODE_CHOICES
        context['crypto_provider_choices'] = [('manual', 'Manual Only'), ('blockcypher', 'BlockCypher')]
        return context


class AdminPlanCreateView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        form = InvestmentPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan created successfully.')
            return redirect(request.POST.get('next') or reverse_lazy('admin_plans'))
        return render(request, 'admin_plans.html', build_plan_page_context(request, create_form=form, open_create_modal=True))


class AdminPlanUpdateView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        plan = get_object_or_404(InvestmentPlan, pk=pk)
        form = InvestmentPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan updated successfully.')
            return redirect(request.POST.get('next') or reverse_lazy('admin_plans'))
        return render(request, 'admin_plans.html', build_plan_page_context(request, plans=_filter_plans_for_request(request), edit_form=form, edit_plan_id=plan.id))


class AdminPlanDeleteView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        plan = get_object_or_404(InvestmentPlan, pk=pk)
        plan.delete()
        messages.success(request, 'Plan deleted successfully.')
        return redirect(request.POST.get('next') or reverse_lazy('admin_plans'))


class DepositApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        deposit.reviewed_by = request.user
        deposit.reviewed_at = timezone.now()
        deposit.review_note = request.POST.get('review_note', '').strip() or 'Approved after manual review.'
        deposit.status = 'completed'
        deposit.save()
        log_action(request.user, 'deposit_completed', 'deposit', deposit.id, {'user': deposit.user.username})
        messages.success(request, 'Deposit completed and credited.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class DepositRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        deposit.reviewed_by = request.user
        deposit.reviewed_at = timezone.now()
        deposit.review_note = request.POST.get('review_note', '').strip() or 'Rejected after manual review.'
        deposit.status = 'rejected'
        deposit.save()
        log_action(request.user, 'deposit_rejected', 'deposit', deposit.id, {'user': deposit.user.username})
        messages.error(request, 'Deposit rejected.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class DepositVerifyView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        if deposit.method != 'automated':
            messages.warning(request, 'Manual deposits are approved directly after staff review.')
            return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))
        try:
            confirmed = verify_and_update_deposit(deposit)
            if confirmed:
                log_action(request.user, 'deposit_completed', 'deposit', deposit.id, {'user': deposit.user.username})
                messages.success(request, 'Deposit verified and completed.')
            else:
                messages.warning(request, 'Deposit not completed yet. Waiting for confirmations.')
        except ProviderError as exc:
            messages.error(request, f'Verification failed: {exc}')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class WithdrawalApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'approved'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        if withdrawal.method == 'automated':
            try:
                process_automated_withdrawal(withdrawal)
                mark_withdrawal_completed(withdrawal)
                messages.success(request, 'Withdrawal approved and completed via automated payout.')
            except ProviderError as exc:
                messages.warning(request, f'Automated payout failed: {exc}')
        else:
            messages.success(request, 'Withdrawal approved.')
        log_action(request.user, 'withdrawal_approved', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class WithdrawalRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'rejected'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        wallet = withdrawal.wallet or Wallet.objects.filter(user=withdrawal.user, wallet_type='primary').first() or Wallet.objects.filter(user=withdrawal.user).first()
        if wallet:
            credit_wallet(wallet, withdrawal.amount, 'profit', 'adjustment', {'reason': 'withdrawal_rejected', 'withdrawal_id': withdrawal.id})
        log_action(request.user, 'withdrawal_rejected', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        messages.error(request, 'Withdrawal rejected.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class WithdrawalPaidView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'completed'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        log_action(request.user, 'withdrawal_completed', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        messages.success(request, 'Withdrawal marked as completed.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class WalletApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        wallet = get_object_or_404(Wallet, pk=pk)
        wallet.is_active = True
        wallet.save(update_fields=['is_active'])
        messages.success(request, 'Wallet activated.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class WalletRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        wallet = get_object_or_404(Wallet, pk=pk)
        wallet.is_active = False
        wallet.save(update_fields=['is_active'])
        messages.error(request, 'Wallet deactivated.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))


class AdminSiteSettingsView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        def upsert_setting(key, value):
            SystemSetting.objects.update_or_create(key=key, defaults={'value': value})

        numeric_settings = {'WELCOME_BONUS', 'MIN_WITHDRAWAL_AMOUNT'}

        settings_map = {
            'PROJECT_NAME': request.POST.get('project_name', '').strip(),
            'SITE_TAGLINE': request.POST.get('site_tagline', '').strip(),
            'SUPPORT_EMAIL': request.POST.get('support_email', '').strip(),
            'SUPPORT_PHONE': request.POST.get('support_phone', '').strip(),
            'SUPPORT_ADDRESS': request.POST.get('support_address', '').strip(),
            'CURRENCY': request.POST.get('currency', '').strip(),
            'WELCOME_BONUS': request.POST.get('welcome_bonus', '').strip(),
            'MIN_WITHDRAWAL_AMOUNT': request.POST.get('min_withdrawal_amount', '').strip(),
            'CRYPTO_PROVIDER': request.POST.get('crypto_provider', '').strip(),
            'BLOCKCYPHER_TOKEN': request.POST.get('blockcypher_token', '').strip(),
            'BLOCKCYPHER_CALLBACK_URL': request.POST.get('blockcypher_callback_url', '').strip(),
            'DESTINATION_BTC_ADDRESS': request.POST.get('destination_btc_address', '').strip(),
            'DESTINATION_ETH_ADDRESS': request.POST.get('destination_eth_address', '').strip(),
            'DESTINATION_USDT_ADDRESS': request.POST.get('destination_usdt_address', '').strip(),
            'GMAIL_CLIENT_ID': request.POST.get('gmail_client_id', '').strip(),
            'GMAIL_CLIENT_SECRET': request.POST.get('gmail_client_secret', '').strip(),
            'GMAIL_REFRESH_TOKEN': request.POST.get('gmail_refresh_token', '').strip(),
            'GMAIL_SENDER_EMAIL': request.POST.get('gmail_sender_email', '').strip(),
            'MANUAL_DEPOSIT_WALLET_ADDRESS': request.POST.get('manual_deposit_wallet_address', '').strip(),
        }
        for key, value in settings_map.items():
            if key in numeric_settings and value == '':
                value = str(get_setting(key, default=DEFAULT_SETTINGS.get(key, '0')))
            upsert_setting(key, value)
        payment_config = get_payment_configuration()
        payment_config.mode = request.POST.get('payment_mode', payment_config.mode)
        payment_config.enable_deposits = 'enable_deposits' in request.POST
        payment_config.enable_withdrawals = 'enable_withdrawals' in request.POST
        payment_config.save(update_fields=['mode', 'enable_deposits', 'enable_withdrawals', 'updated_at'])
        messages.success(request, 'Site settings updated.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard'))
