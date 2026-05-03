from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.db.models import Count
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.db.models.functions import TruncDate
from datetime import timedelta

from investments.models import InvestmentPlan
from investments.services import sync_investment_profits, PROFIT_SYNC_SUMMARY_CACHE_KEY
from deposits.models import Deposit
from withdrawals.models import Withdrawal
from kyc.models import KYCProfile
from wallets.models import Wallet
from payments.models import CryptoCurrency, PaymentConfiguration
from settingsconfig.utils import DEFAULT_SETTINGS, get_setting
from adminpanel.models import AuditLog
from django.contrib.auth.models import User


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class AdminDashboardView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'admin_dashboard.html'

    @staticmethod
    def _line_path(values, width=420, height=220, padding=16):
        points = list(values)
        if not points:
            return '', ''
        max_value = max(points) or 1
        span_x = width - (padding * 2)
        span_y = height - (padding * 2)
        denom = max(len(points) - 1, 1)
        coords = []
        for index, value in enumerate(points):
            x = padding + (span_x * index / denom)
            y = height - padding - (span_y * (value / max_value if max_value else 0))
            coords.append(f"{x:.1f},{y:.1f}")
        area = f"M {padding},{height - padding} L " + " L ".join(coords) + f" L {width - padding},{height - padding} Z"
        line = "M " + " L ".join(coords)
        return area, line

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_deposits = Deposit.objects.select_related('user', 'wallet', 'crypto').filter(status__in=['pending', 'confirming']).order_by('-created_at')
        pending_withdrawals = Withdrawal.objects.select_related('user', 'wallet', 'crypto').filter(status='pending').order_by('-created_at')
        pending_kyc = KYCProfile.objects.select_related('user').filter(status='pending').order_by('-submitted_at')
        pending_wallets = Wallet.objects.select_related('user').filter(is_active=False).order_by('-created_at')
        total_users = User.objects.count()
        staff_users = User.objects.filter(is_staff=True).count()
        active_plans = InvestmentPlan.objects.filter(is_active=True).count()
        active_cryptos = CryptoCurrency.objects.filter(is_active=True).count()
        total_audit_logs = AuditLog.objects.count()
        profit_sync_summary = cache.get(PROFIT_SYNC_SUMMARY_CACHE_KEY)
        today = timezone.localdate()
        days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        date_window = (days[0], days[-1])

        def daily_counts(queryset, date_field):
            data = queryset.filter(**{f'{date_field}__date__range': date_window}).annotate(day=TruncDate(date_field)).values('day').annotate(total=Count('id'))
            return {row['day']: row['total'] for row in data}

        incoming_maps = [
            daily_counts(Deposit.objects.all(), 'created_at'),
            daily_counts(Withdrawal.objects.all(), 'created_at'),
            daily_counts(KYCProfile.objects.all(), 'submitted_at'),
        ]
        resolved_maps = [
            daily_counts(Deposit.objects.exclude(reviewed_at__isnull=True), 'reviewed_at'),
            daily_counts(Withdrawal.objects.exclude(processed_at__isnull=True), 'processed_at'),
            daily_counts(KYCProfile.objects.exclude(reviewed_at__isnull=True), 'reviewed_at'),
        ]
        incoming_series = [sum(m.get(day, 0) for m in incoming_maps) for day in days]
        resolved_series = [sum(m.get(day, 0) for m in resolved_maps) for day in days]
        incoming_area_path, incoming_line_path = self._line_path(incoming_series)
        resolved_area_path, resolved_line_path = self._line_path(resolved_series)
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
            'GMAIL_SENDER_EMAIL',
            'MANUAL_DEPOSIT_WALLET_ADDRESS',
        ]
        site_settings = {key: get_setting(key, default=DEFAULT_SETTINGS.get(key, '')) for key in site_keys}
        payment_config = PaymentConfiguration.objects.first()
        queue_sources = [
            ('KYC', pending_kyc.count(), 'admin_kyc_reviews', 'warning'),
            ('Deposits', pending_deposits.count(), 'admin_pending_deposits', 'warning'),
            ('Withdrawals', pending_withdrawals.count(), 'admin_pending_withdrawals', 'warning'),
            ('Wallets', pending_wallets.count(), 'admin_wallets', 'warning'),
        ]
        chart_sources = [
            ('Users', total_users),
            ('Staff', staff_users),
            ('Plans', active_plans),
            ('Cryptos', active_cryptos),
            ('Audit', total_audit_logs),
        ]
        queue_peak = max((count for _, count, _, _ in queue_sources), default=0)
        chart_peak = max((count for _, count in chart_sources), default=0)
        context.update(
            counts={
                'deposits': pending_deposits.count(),
                'withdrawals': pending_withdrawals.count(),
                'kyc': pending_kyc.count(),
                'wallets': pending_wallets.count(),
                'users': total_users,
                'staff': staff_users,
                'active_plans': active_plans,
                'active_cryptos': active_cryptos,
                'audit_logs': total_audit_logs,
            },
            now=timezone.now(),
            profit_sync_summary=profit_sync_summary,
            pending_kyc_profiles=pending_kyc[:5],
            pending_deposit_items=pending_deposits[:5],
            pending_withdrawal_items=pending_withdrawals[:5],
            inactive_wallet_items=pending_wallets[:5],
            recent_audit_logs=AuditLog.objects.select_related('actor').order_by('-created_at')[:6],
            site_settings=site_settings,
            payment_config=payment_config,
            payment_mode_choices=PaymentConfiguration.MODE_CHOICES,
            trend_days=[day.strftime('%b %d') for day in days],
            trend_incoming_series=incoming_series,
            trend_resolved_series=resolved_series,
            trend_incoming_area_path=incoming_area_path,
            trend_incoming_line_path=incoming_line_path,
            trend_resolved_area_path=resolved_area_path,
            trend_resolved_line_path=resolved_line_path,
            trend_incoming_total=sum(incoming_series),
            trend_resolved_total=sum(resolved_series),
            queue_insights=[
                {
                    'label': label,
                    'count': count,
                    'url': url,
                    'tone': tone,
                    'height': 22 if queue_peak == 0 else max(22, round((count / queue_peak) * 100)),
                    'percent': 22 if queue_peak == 0 else max(22, round((count / queue_peak) * 100)),
                    'note': 'Review next' if count else 'All clear',
                }
                for label, count, url, tone in queue_sources
            ],
            platform_insights=[
                {
                    'label': label,
                    'count': count,
                    'height': 22 if chart_peak == 0 else max(22, round((count / chart_peak) * 100)),
                }
                for label, count in chart_sources
            ],
        )
        return context


class InvestmentProfitSyncView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request):
        sync_investment_profits(process_date=timezone.now().date())
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or '/staff/')
