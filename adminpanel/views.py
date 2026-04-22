from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.core.files.storage import default_storage
from uuid import uuid4
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView
from django.http import HttpResponse
from django.db.models import Q, Count, Sum

from adminpanel.models import AuditLog
from adminpanel.utils import log_action
from deposits.services import verify_and_update_deposit, ProviderError
from deposits.models import Deposit
from withdrawals.models import Withdrawal
from wallets.models import Wallet
from wallets.services import credit_wallet
from accounts.services import create_notification
from payments.models import CryptoCurrency, PaymentConfiguration
from payments.services import get_payment_configuration
from settingsconfig.models import SystemSetting
from settingsconfig.utils import DEFAULT_SETTINGS, get_setting
from django.core.mail import send_mail
from django.conf import settings
from kyc.models import KYCProfile
from accounts.models import LoginLog
from django.contrib.auth.models import User
from investments.models import InvestmentPlan, UserInvestment
from investments.forms import InvestmentPlanForm
from investments.services import sync_investment_profits
from wallets.models import Wallet


def build_admin_operations_context(
    request,
    *,
    plan_form=None,
    open_create_modal=False,
    edit_plan_id=None,
    edit_form=None,
    active_tab='kyc',
):
    kyc_status = request.GET.get('kyc_status', '').strip()
    kyc_query = request.GET.get('kyc_q', '').strip()
    dep_status = request.GET.get('dep_status', '').strip()
    dep_query = request.GET.get('dep_q', '').strip()
    dep_crypto = request.GET.get('dep_crypto', '').strip()
    wd_status = request.GET.get('wd_status', '').strip()
    wd_query = request.GET.get('wd_q', '').strip()

    kyc_queryset = KYCProfile.objects.select_related('user').order_by('-submitted_at')
    if kyc_status:
        kyc_queryset = kyc_queryset.filter(status=kyc_status)
    if kyc_query:
        kyc_queryset = kyc_queryset.filter(
            Q(user__username__icontains=kyc_query)
            | Q(full_name__icontains=kyc_query)
            | Q(id_number__icontains=kyc_query)
        )

    deposit_queryset = Deposit.objects.select_related('user', 'wallet', 'crypto').order_by('-created_at')
    if dep_status:
        deposit_queryset = deposit_queryset.filter(status=dep_status)
    if dep_crypto:
        deposit_queryset = deposit_queryset.filter(crypto_id=dep_crypto)
    if dep_query:
        deposit_queryset = deposit_queryset.filter(
            Q(user__username__icontains=dep_query) | Q(transaction_hash__icontains=dep_query)
        )

    withdrawal_queryset = Withdrawal.objects.select_related('user', 'wallet', 'crypto').order_by('-created_at')
    if wd_status:
        withdrawal_queryset = withdrawal_queryset.filter(status=wd_status)
    if wd_query:
        withdrawal_queryset = withdrawal_queryset.filter(
            Q(user__username__icontains=wd_query) | Q(wallet_address__icontains=wd_query)
        )

    plans = InvestmentPlan.objects.all().order_by('min_amount')
    plan_forms = [(plan, InvestmentPlanForm(instance=plan)) for plan in plans]

    total_users = User.objects.count()
    total_invested = UserInvestment.objects.aggregate(total=Sum('amount'))['total'] or 0
    pending_deposits = Deposit.objects.filter(status='pending').count()
    pending_withdrawals = Withdrawal.objects.filter(status='pending').count()
    pending_kyc = KYCProfile.objects.filter(status='pending').count()
    active_plans = InvestmentPlan.objects.filter(is_active=True).count()
    kyc_counts = {
        'total': KYCProfile.objects.count(),
        'pending': pending_kyc,
        'verified': KYCProfile.objects.filter(status='verified').count(),
        'rejected': KYCProfile.objects.filter(status='rejected').count(),
    }
    deposit_counts = {
        'total': Deposit.objects.count(),
        'pending': pending_deposits,
        'confirming': Deposit.objects.filter(status='confirming').count(),
        'completed': Deposit.objects.filter(status='completed').count(),
        'rejected': Deposit.objects.filter(status='rejected').count(),
    }
    withdrawal_counts = {
        'total': Withdrawal.objects.count(),
        'pending': Withdrawal.objects.filter(status='pending').count(),
        'approved': Withdrawal.objects.filter(status='approved').count(),
        'completed': Withdrawal.objects.filter(status='completed').count(),
        'rejected': Withdrawal.objects.filter(status='rejected').count(),
    }
    plan_counts = {
        'total': InvestmentPlan.objects.count(),
        'active': active_plans,
        'paused': InvestmentPlan.objects.filter(is_active=False).count(),
        'premium': InvestmentPlan.objects.filter(plan_tier__in=['premium', 'vip']).count(),
    }
    wallet_status = request.GET.get('wallet_status', '').strip()
    wallet_query = request.GET.get('wallet_q', '').strip()
    wallets_qs = Wallet.objects.select_related('user').order_by('-created_at')
    if wallet_status == 'active':
        wallets_qs = wallets_qs.filter(is_active=True)
    elif wallet_status == 'inactive':
        wallets_qs = wallets_qs.filter(is_active=False)
    if wallet_query:
        wallets_qs = wallets_qs.filter(Q(user__username__icontains=wallet_query) | Q(name__icontains=wallet_query))
    wallet_counts = {
        'total': Wallet.objects.count(),
        'active': Wallet.objects.filter(is_active=True).count(),
        'inactive': Wallet.objects.filter(is_active=False).count(),
    }

    site_keys = [
        'PROJECT_NAME',
        'SITE_TAGLINE',
        'SITE_LOGO',
        'SITE_FAVICON',
        'SUPPORT_EMAIL',
        'SUPPORT_PHONE',
        'SUPPORT_ADDRESS',
        'CURRENCY',
        'WELCOME_BONUS',
        'BONUS_PROFIT_MULTIPLIER',
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
    site_settings = {
        key: get_setting(key, default=DEFAULT_SETTINGS.get(key, '')) for key in site_keys
    }
    payment_config = get_payment_configuration()

    return {
        'admin_tab': active_tab,
        'kyc_profiles': kyc_queryset[:20],
        'kyc_status_choices': KYCProfile.STATUS_CHOICES,
        'kyc_status': kyc_status,
        'kyc_q': kyc_query,
        'deposits': deposit_queryset[:20],
        'deposit_status_choices': Deposit.STATUS_CHOICES,
        'deposit_crypto_choices': CryptoCurrency.objects.filter(is_active=True).order_by('symbol', 'network'),
        'dep_status': dep_status,
        'dep_q': dep_query,
        'dep_crypto': dep_crypto,
        'withdrawals': withdrawal_queryset[:20],
        'withdrawal_status_choices': Withdrawal.STATUS_CHOICES,
        'wd_status': wd_status,
        'wd_q': wd_query,
        'plans': plans,
        'plan_forms': plan_forms,
        'create_form': plan_form or InvestmentPlanForm(),
        'open_create_modal': open_create_modal,
        'edit_plan_id': edit_plan_id,
        'edit_form': edit_form,
        'counts': {
            'users': total_users,
            'invested': total_invested,
            'pending_deposits': pending_deposits,
            'pending_withdrawals': pending_withdrawals,
            'pending_kyc': pending_kyc,
            'active_plans': active_plans,
        },
        'kyc_counts': kyc_counts,
        'deposit_counts': deposit_counts,
        'withdrawal_counts': withdrawal_counts,
        'plan_counts': plan_counts,
        'wallets': wallets_qs[:20],
        'wallet_status_choices': [('active', 'Active'), ('inactive', 'Inactive')],
        'wallet_status': wallet_status,
        'wallet_q': wallet_query,
        'wallet_counts': wallet_counts,
        'site_settings': site_settings,
        'payment_config': payment_config,
        'payment_mode_choices': PaymentConfiguration.MODE_CHOICES,
        'crypto_provider_choices': [
            ('manual', 'Manual Only'),
            ('blockcypher', 'BlockCypher'),
        ],
    }


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class AdminDashboardView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'admin_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_deposits = Deposit.objects.filter(status__in=['pending', 'confirming'])
        pending_withdrawals = Withdrawal.objects.filter(status__in=['pending'])
        pending_kyc = KYCProfile.objects.filter(status='pending')
        pending_wallets = Wallet.objects.filter(is_active=False)
        total_users = User.objects.count()
        total_invested = UserInvestment.objects.aggregate(total=Sum('amount'))['total'] or 0
        active_plans = InvestmentPlan.objects.filter(is_active=True).count()
        context.update(
            counts={
                'deposits': pending_deposits.count(),
                'withdrawals': pending_withdrawals.count(),
                'kyc': pending_kyc.count(),
                'wallets': pending_wallets.count(),
                'users': total_users,
                'invested': total_invested,
                'active_plans': active_plans,
            },
            now=timezone.now(),
        )
        return context


class AdminOperationsView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'admin_operations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_tab = self.request.GET.get('tab', 'kyc')
        context.update(build_admin_operations_context(self.request, active_tab=active_tab))
        return context


class InvestmentProfitSyncView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        summary = sync_investment_profits(process_date=timezone.now().date())
        messages.success(
            request,
            (
                f"Profit sync complete. Payouts credited: {summary['payouts_created']}. "
                f"Investments completed: {summary['investments_completed']}."
            ),
        )
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse_lazy('admin_dashboard')
        return redirect(next_url)


class AdminSiteSettingsView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        def upsert_setting(key, value):
            SystemSetting.objects.update_or_create(key=key, defaults={'value': value})

        settings_map = {
            'PROJECT_NAME': request.POST.get('project_name', '').strip(),
            'SITE_TAGLINE': request.POST.get('site_tagline', '').strip(),
            'SUPPORT_EMAIL': request.POST.get('support_email', '').strip(),
            'SUPPORT_PHONE': request.POST.get('support_phone', '').strip(),
            'SUPPORT_ADDRESS': request.POST.get('support_address', '').strip(),
            'CURRENCY': request.POST.get('currency', '').strip(),
            'WELCOME_BONUS': request.POST.get('welcome_bonus', '').strip(),
            'BONUS_PROFIT_MULTIPLIER': request.POST.get('bonus_profit_multiplier', '').strip(),
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
            upsert_setting(key, value)

        logo_file = request.FILES.get('site_logo')
        if logo_file:
            logo_path = default_storage.save(
                f"site/{uuid4().hex}_{logo_file.name}",
                logo_file,
            )
            upsert_setting('SITE_LOGO', default_storage.url(logo_path))

        favicon_file = request.FILES.get('site_favicon')
        if favicon_file:
            favicon_path = default_storage.save(
                f"site/{uuid4().hex}_{favicon_file.name}",
                favicon_file,
            )
            upsert_setting('SITE_FAVICON', default_storage.url(favicon_path))

        payment_config = get_payment_configuration()
        mode = request.POST.get('payment_mode', '').strip()
        valid_modes = {choice[0] for choice in PaymentConfiguration.MODE_CHOICES}
        if mode in valid_modes:
            payment_config.mode = mode
        payment_config.enable_deposits = 'enable_deposits' in request.POST
        payment_config.enable_withdrawals = 'enable_withdrawals' in request.POST
        payment_config.save(update_fields=['mode', 'enable_deposits', 'enable_withdrawals', 'updated_at'])

        log_action(request.user, 'settings_changed', 'settings', 0, {'section': 'site_management'})
        messages.success(request, "Site settings updated.")
        return redirect(f"{reverse_lazy('admin_operations')}?tab=site")


class WalletApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        wallet = get_object_or_404(Wallet, pk=pk)
        wallet.is_active = True
        wallet.save(update_fields=['is_active'])
        messages.success(request, "Wallet activated.")
        create_notification(
            wallet.user,
            "Wallet activated",
            f"Your wallet {wallet.name} is now active.",
            level='success',
        )
        if wallet.user.email:
            send_mail(
                "Wallet activated",
                f"Hello {wallet.user.username}, your wallet \"{wallet.name}\" has been activated and is now active.",
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                [wallet.user.email],
                fail_silently=True,
            )
        return redirect(f"{reverse_lazy('admin_operations')}?tab=wallets")


class WalletRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        wallet = get_object_or_404(Wallet, pk=pk)
        wallet.is_active = False
        wallet.save(update_fields=['is_active'])
        messages.error(request, "Wallet deactivated.")
        create_notification(
            wallet.user,
            "Wallet deactivated",
            f"Your wallet {wallet.name} was deactivated. Please contact support if needed.",
            level='warning',
        )
        if wallet.user.email:
            send_mail(
                "Wallet deactivated",
                f"Hello {wallet.user.username}, your wallet \"{wallet.name}\" was deactivated. Please contact support if you need help.",
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                [wallet.user.email],
                fail_silently=True,
            )
        return redirect(f"{reverse_lazy('admin_operations')}?tab=wallets")


class AuditLogListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'audit_logs.html'
    model = AuditLog
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        return AuditLog.objects.select_related('actor').order_by('-created_at')


class PendingDepositsView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'pending_deposits.html'
    model = Deposit
    context_object_name = 'deposits'
    paginate_by = 25

    def get_queryset(self):
        queryset = Deposit.objects.all().order_by('-created_at')
        status = self.request.GET.get('status', 'pending')
        query = self.request.GET.get('q', '').strip()
        crypto = self.request.GET.get('crypto', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        if crypto:
            queryset = queryset.filter(crypto_id=crypto)
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(transaction_hash__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Deposit.STATUS_CHOICES
        context['crypto_choices'] = CryptoCurrency.objects.filter(is_active=True).order_by('symbol', 'network')
        return context


class PendingWithdrawalsView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'pending_withdrawals.html'
    model = Withdrawal
    context_object_name = 'withdrawals'
    paginate_by = 25

    def get_queryset(self):
        queryset = Withdrawal.objects.all().order_by('-created_at')
        status = self.request.GET.get('status', 'pending')
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


class KYCReviewListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'kyc_reviews.html'
    model = KYCProfile
    context_object_name = 'kyc_profiles'
    paginate_by = 25

    def get_queryset(self):
        status = self.request.GET.get('status', 'pending')
        query = self.request.GET.get('q', '').strip()
        queryset = KYCProfile.objects.select_related('user').order_by('-submitted_at')
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(full_name__icontains=query) | Q(id_number__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = KYCProfile.STATUS_CHOICES
        return context


class KYCApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        if profile.completion_percent() < 100:
            messages.error(request, "KYC cannot be verified until it is 100% complete.")
            return redirect(f"{reverse_lazy('admin_operations')}?tab=kyc")
        profile.status = 'verified'
        profile.reviewed_at = timezone.now()
        profile.review_note = request.POST.get('review_note', '')
        profile.save(update_fields=['status', 'reviewed_at', 'review_note'])
        log_action(request.user, 'kyc_approved', 'kyc', profile.id, {'user': profile.user.username})
        messages.success(request, "KYC approved.")
        create_notification(
            profile.user,
            "KYC approved",
            "Your identity verification has been approved.",
            level='success',
        )
        return redirect(f"{reverse_lazy('admin_operations')}?tab=kyc")


class KYCRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        profile.status = 'rejected'
        profile.reviewed_at = timezone.now()
        profile.review_note = request.POST.get('review_note', '')
        profile.save(update_fields=['status', 'reviewed_at', 'review_note'])
        log_action(request.user, 'kyc_rejected', 'kyc', profile.id, {'user': profile.user.username})
        messages.error(request, "KYC rejected.")
        create_notification(
            profile.user,
            "KYC rejected",
            "Your verification was rejected. Please update your details and resubmit.",
            level='warning',
        )
        return redirect(f"{reverse_lazy('admin_operations')}?tab=kyc")


class RiskDashboardView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'risk_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        risky_users = []
        users = User.objects.all()
        for user in users:
            reasons = []
            kyc = KYCProfile.objects.filter(user=user).first()
            if kyc and kyc.status != 'verified':
                pending_withdrawals = Withdrawal.objects.filter(user=user, status='pending').count()
                if pending_withdrawals:
                    reasons.append("Withdrawals pending without verified KYC")
            ip_count = LoginLog.objects.filter(user=user).values('ip_address').distinct().count()
            if ip_count >= 4:
                reasons.append("Multiple IP logins detected")
            if reasons:
                risky_users.append({'user': user, 'reasons': reasons})
        context['risky_users'] = risky_users
        return context


class AuditLogExportView(LoginRequiredMixin, StaffOnlyMixin, View):
    def get(self, request):
        logs = AuditLog.objects.select_related('actor').order_by('-created_at')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        response.write("timestamp,actor,action,entity,entity_id,meta\n")
        for log in logs:
            response.write(
                f"{log.created_at},{log.actor.username if log.actor else ''},{log.action},{log.entity},{log.entity_id},{log.meta}\n"
            )
        return response


class AdminPlanListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'admin_plans.html'
    model = InvestmentPlan
    context_object_name = 'plans'
    paginate_by = 20

    def get_queryset(self):
        return InvestmentPlan.objects.all().order_by('min_amount')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = InvestmentPlanForm()
        context['open_create_modal'] = False
        context['edit_plan_id'] = None
        context['edit_form'] = None
        context['plan_forms'] = [(plan, InvestmentPlanForm(instance=plan)) for plan in context['plans']]
        return context


class AdminPlanCreateView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        form = InvestmentPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan created successfully.")
            return redirect(f"{reverse_lazy('admin_operations')}?tab=plans")

        context = build_admin_operations_context(
            request,
            plan_form=form,
            open_create_modal=True,
            edit_plan_id=None,
            edit_form=None,
            active_tab='plans',
        )
        return render(request, 'admin_operations.html', context)


class AdminPlanUpdateView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        plan = get_object_or_404(InvestmentPlan, pk=pk)
        form = InvestmentPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan updated successfully.")
            return redirect(f"{reverse_lazy('admin_operations')}?tab=plans")

        context = build_admin_operations_context(
            request,
            plan_form=InvestmentPlanForm(),
            open_create_modal=False,
            edit_plan_id=plan.id,
            edit_form=form,
            active_tab='plans',
        )
        plan_forms = []
        for item in context['plans']:
            if item.id == plan.id:
                plan_forms.append((item, form))
            else:
                plan_forms.append((item, InvestmentPlanForm(instance=item)))
        context['plan_forms'] = plan_forms
        return render(request, 'admin_operations.html', context)


class AdminPlanDeleteView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        plan = get_object_or_404(InvestmentPlan, pk=pk)
        plan.delete()
        messages.success(request, "Plan deleted successfully.")
        return redirect(f"{reverse_lazy('admin_operations')}?tab=plans")


class DepositApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        deposit.status = 'completed'
        deposit.save()
        log_action(request.user, 'deposit_completed', 'deposit', deposit.id, {'user': deposit.user.username})
        messages.success(request, "Deposit completed and credited.")
        tab = request.GET.get('tab', 'deposits')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class DepositRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        deposit.status = 'rejected'
        deposit.save()
        log_action(request.user, 'deposit_rejected', 'deposit', deposit.id, {'user': deposit.user.username})
        messages.error(request, "Deposit rejected.")
        tab = request.GET.get('tab', 'deposits')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class DepositVerifyView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        deposit = get_object_or_404(Deposit, pk=pk)
        if deposit.method != 'automated':
            messages.warning(request, "Manual deposits must be reviewed and approved manually.")
            tab = request.GET.get('tab', 'deposits')
            return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")
        try:
            confirmed = verify_and_update_deposit(deposit)
            if confirmed:
                log_action(request.user, 'deposit_completed', 'deposit', deposit.id, {'user': deposit.user.username})
                messages.success(request, "Deposit verified and completed.")
            else:
                messages.warning(request, "Deposit not completed yet. Waiting for confirmations.")
        except ProviderError as exc:
            messages.error(request, f"Verification failed: {exc}")
        tab = request.GET.get('tab', 'deposits')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class WithdrawalApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'approved'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        if withdrawal.method == 'automated':
            from withdrawals.services import process_automated_withdrawal, ProviderError, mark_withdrawal_completed
            try:
                process_automated_withdrawal(withdrawal)
                mark_withdrawal_completed(withdrawal)
                messages.success(request, "Withdrawal approved and completed via automated payout.")
            except ProviderError as exc:
                messages.warning(request, f"Automated payout failed: {exc}")
        else:
            messages.success(request, "Withdrawal approved.")
        log_action(request.user, 'withdrawal_approved', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        tab = request.GET.get('tab', 'withdrawals')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class WithdrawalRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'rejected'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        wallet = (
            withdrawal.wallet
            or Wallet.objects.filter(user=withdrawal.user, wallet_type='primary').first()
            or Wallet.objects.filter(user=withdrawal.user).first()
        )
        if wallet:
            credit_wallet(wallet, withdrawal.amount, 'profit', 'adjustment', {'reason': 'withdrawal_rejected', 'withdrawal_id': withdrawal.id})
        log_action(request.user, 'withdrawal_rejected', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        messages.error(request, "Withdrawal rejected.")
        tab = request.GET.get('tab', 'withdrawals')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class WithdrawalPaidView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        withdrawal.status = 'completed'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        log_action(request.user, 'withdrawal_completed', 'withdrawal', withdrawal.id, {'user': withdrawal.user.username})
        messages.success(request, "Withdrawal marked as completed.")
        tab = request.GET.get('tab', 'withdrawals')
        return redirect(f"{reverse_lazy('admin_operations')}?tab={tab}")


class KYCDownloadView(LoginRequiredMixin, StaffOnlyMixin, View):
    def get(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        response = HttpResponse(content_type='text/plain')
        filename = f"kyc_{profile.user.username}_{profile.id}.txt"
        response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
        lines = [
            f"User: {profile.user.username}",
            f"Status: {profile.get_status_display()}",
            f"Full name: {profile.full_name}",
            f"Date of birth: {profile.date_of_birth or ''}",
            f"Country: {profile.country}",
            f"Country of residence: {profile.country_of_residence}",
            f"ID type: {profile.get_id_type_display()}",
            f"ID number: {profile.id_number}",
            f"Address line: {profile.address_line}",
            f"City: {profile.city}",
            f"Postal code: {profile.postal_code}",
            f"Phone: {profile.phone_number}",
            f"Source of funds: {profile.source_of_funds}",
            f"Source of funds (other): {profile.source_of_funds_other}",
            f"Tax ID: {profile.tax_id}",
            f"Submitted at: {profile.submitted_at or ''}",
            f"Reviewed at: {profile.reviewed_at or ''}",
            f"Review note: {profile.review_note}",
        ]
        response.write("\n".join(lines))
        response.write("\n\nDocuments:\n")
        if profile.id_document_front:
            response.write(f"ID front: {request.build_absolute_uri(profile.id_document_front.url)}\n")
        if profile.id_document_back:
            response.write(f"ID back: {request.build_absolute_uri(profile.id_document_back.url)}\n")
        if profile.selfie_photo:
            response.write(f"Selfie: {request.build_absolute_uri(profile.selfie_photo.url)}\n")
        return response

# Create your views here.
