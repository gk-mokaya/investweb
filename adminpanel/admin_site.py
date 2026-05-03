from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import AuditLog
from accounts.models import LoginLog, UserProfile
from deposits.models import Deposit
from investments.models import InvestmentPlan, UserInvestment
from kyc.models import KYCProfile
from payments.models import CryptoCurrency, PaymentConfiguration
from settingsconfig.models import SystemSetting
from wallets.models import Wallet
from withdrawals.models import Withdrawal


class PlatformAdminSite(admin.AdminSite):
    site_header = 'Invest Control Room'
    site_title = 'Invest Control Room'
    index_title = 'Operations Command Center'
    index_template = 'admin/index.html'
    site_url = '/'

    def _dashboard_cards(self):
        total_users = User.objects.count()
        staff_users = User.objects.filter(is_staff=True).count()
        inactive_users = User.objects.filter(is_active=False).count()
        total_invested = UserInvestment.objects.aggregate(total=Sum('amount'))['total'] or 0
        pending_kyc = KYCProfile.objects.filter(status='pending').count()
        pending_deposits = Deposit.objects.filter(status='pending').count()
        pending_withdrawals = Withdrawal.objects.filter(status='pending').count()
        active_wallets = Wallet.objects.filter(is_active=True).count()
        active_plans = InvestmentPlan.objects.filter(is_active=True).count()

        return [
            {
                'label': 'Users',
                'value': total_users,
                'meta': f'{staff_users} staff, {inactive_users} inactive',
                'url': reverse('admin:auth_user_changelist'),
                'tone': 'primary',
            },
            {
                'label': 'Invested Capital',
                'value': f"{total_invested}",
                'meta': 'Across all active portfolios',
                'url': reverse('admin:investments_userinvestment_changelist'),
                'tone': 'success',
            },
            {
                'label': 'Pending KYC',
                'value': pending_kyc,
                'meta': 'Identity reviews waiting',
                'url': reverse('admin:kyc_kycprofile_changelist'),
                'tone': 'warning',
            },
            {
                'label': 'Pending Deposits',
                'value': pending_deposits,
                'meta': 'Awaiting review or confirmation',
                'url': reverse('admin:deposits_deposit_changelist'),
                'tone': 'warning',
            },
            {
                'label': 'Pending Withdrawals',
                'value': pending_withdrawals,
                'meta': 'Review queue for payouts',
                'url': reverse('admin:withdrawals_withdrawal_changelist'),
                'tone': 'warning',
            },
            {
                'label': 'Wallets',
                'value': active_wallets,
                'meta': 'Active wallet records',
                'url': reverse('admin:wallets_wallet_changelist'),
                'tone': 'info',
            },
            {
                'label': 'Active Plans',
                'value': active_plans,
                'meta': 'Live investment products',
                'url': reverse('admin:investments_investmentplan_changelist'),
                'tone': 'info',
            },
            {
                'label': 'Security Events',
                'value': LoginLog.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count(),
                'meta': 'Logins captured in the last 7 days',
                'url': reverse('admin:accounts_loginlog_changelist'),
                'tone': 'primary',
            },
        ]

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(
            dashboard_cards=self._dashboard_cards(),
            recent_users=User.objects.select_related('userprofile').order_by('-date_joined')[:8],
            recent_deposits=Deposit.objects.select_related('user', 'crypto', 'wallet').order_by('-created_at')[:8],
            recent_withdrawals=Withdrawal.objects.select_related('user', 'crypto', 'wallet').order_by('-created_at')[:8],
            recent_kyc=KYCProfile.objects.select_related('user').order_by('-submitted_at')[:8],
            recent_logs=AuditLog.objects.select_related('actor').order_by('-created_at')[:8],
            recent_wallets=Wallet.objects.select_related('user').order_by('-created_at')[:8],
            recent_settings=SystemSetting.objects.order_by('-updated_at')[:6],
            payment_config=PaymentConfiguration.objects.first(),
            crypto_count=CryptoCurrency.objects.count(),
        )
        return super().index(request, extra_context)


platform_admin_site = PlatformAdminSite(name='platform_admin')

