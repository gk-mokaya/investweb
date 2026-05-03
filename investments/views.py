from decimal import Decimal
from collections import defaultdict
from decimal import Decimal
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView
from django.db.models.functions import TruncDate

from investments.forms import CreateInvestmentForm, InvestmentPlanForm
from investments.models import InvestmentPlan, UserInvestment, DailyProfit
from investments.services import create_investment
from accounts.services import create_notification
from accounts.models import UserProfile
from deposits.models import Deposit
from wallets.models import Wallet
from wallets.services import get_primary_wallet
from settingsconfig.utils import get_setting, get_setting_decimal
from withdrawals.models import Withdrawal


def attach_profit_schedule(investments, max_rows=30):
    items = list(investments)
    if not items:
        return items
    ids = [inv.id for inv in items]
    schedule_map = defaultdict(list)
    profits = DailyProfit.objects.filter(investment_id__in=ids).order_by('date')
    for profit in profits:
        if max_rows is None:
            schedule_map[profit.investment_id].append(profit)
        elif len(schedule_map[profit.investment_id]) < max_rows:
            schedule_map[profit.investment_id].append(profit)
    for inv in items:
        inv.profit_schedule = schedule_map.get(inv.id, [])
    return items


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    @staticmethod
    def _line_path(values, width=420, height=220, padding=16):
        points = list(values)
        if not points:
            return '', ''
        max_value = max(points) or Decimal('1')
        span_x = width - (padding * 2)
        span_y = height - (padding * 2)
        denom = max(len(points) - 1, 1)
        coords = []
        for index, value in enumerate(points):
            x = padding + (span_x * index / denom)
            y = height - padding - (span_y * (float(value) / float(max_value) if max_value else 0))
            coords.append(f"{x:.1f},{y:.1f}")
        area = f"M {padding},{height - padding} L " + " L ".join(coords) + f" L {width - padding},{height - padding} Z"
        line = "M " + " L ".join(coords)
        return area, line

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet = get_primary_wallet(self.request.user)
        investments_qs = UserInvestment.objects.filter(user=self.request.user).select_related('plan', 'wallet').order_by('-start_date')
        active_investments = investments_qs.filter(is_completed=False)
        total_invested = investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_earned = investments_qs.aggregate(total=Sum('total_earned'))['total'] or Decimal('0')
        active_investments_count = active_investments.count()
        plan_allocation_qs = list(
            investments_qs.values('plan__name').annotate(total=Sum('amount')).order_by('-total')[:5]
        )
        recent_investments = []
        for investment in investments_qs[:3]:
            duration_days = max((investment.end_date - investment.start_date).days, 1)
            elapsed_days = max((timezone.now() - investment.start_date).days, 0)
            progress = min(100, round((elapsed_days / duration_days) * 100))
            days_left = max((investment.end_date - timezone.now()).days, 0)
            recent_investments.append(
                {
                    'investment': investment,
                    'progress': progress,
                    'days_left': days_left,
                }
            )
        next_maturity = active_investments.order_by('end_date').first()
        profile = UserProfile.objects.filter(user=self.request.user).first()
        bonus_balance = wallet.bonus_balance if wallet else Decimal('0')
        bonus_active = bool(wallet and bonus_balance > 0 and profile and not profile.has_withdrawn)
        today = timezone.localdate()
        raw_start = self.request.GET.get('start_date', '').strip()
        raw_end = self.request.GET.get('end_date', '').strip()

        def parse_date(value):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None

        selected_start = parse_date(raw_start) or (today - timedelta(days=6))
        selected_end = parse_date(raw_end) or today
        if selected_end < selected_start:
            selected_start, selected_end = selected_end, selected_start
        max_window = timedelta(days=90)
        if selected_end - selected_start > max_window:
            selected_end = selected_start + max_window
        days = [selected_start + timedelta(days=offset) for offset in range((selected_end - selected_start).days + 1)]
        date_window = (days[0], days[-1])

        def daily_amounts_datetime(queryset, date_field):
            data = (
                queryset.filter(**{f'{date_field}__date__range': date_window})
                .annotate(day=TruncDate(date_field))
                .values('day')
                .annotate(total=Sum('amount'))
            )
            return {row['day']: (row['total'] or Decimal('0')) for row in data}

        def daily_amounts_date(queryset, date_field):
            data = (
                queryset.filter(**{f'{date_field}__range': date_window})
                .values('date')
                .annotate(total=Sum('amount'))
            )
            return {row['date']: (row['total'] or Decimal('0')) for row in data}

        deposit_map = daily_amounts_datetime(
            Deposit.objects.filter(user=self.request.user, status='completed', completed_at__isnull=False),
            'completed_at',
        )
        withdrawal_map = daily_amounts_datetime(
            Withdrawal.objects.filter(user=self.request.user, status__in=['approved', 'completed']),
            'created_at',
        )
        profit_map = daily_amounts_date(
            DailyProfit.objects.filter(investment__user=self.request.user),
            'date',
        )
        activity_days = [day.strftime('%b %d') for day in days]
        if len(days) <= 7:
            activity_axis_labels = activity_days
        else:
            sample_indexes = sorted(
                {
                    round(index * (len(days) - 1) / 6)
                    for index in range(7)
                }
            )
            activity_axis_labels = [activity_days[index] for index in sample_indexes]
        activity_deposits = [deposit_map.get(day, Decimal('0')) for day in days]
        activity_withdrawals = [withdrawal_map.get(day, Decimal('0')) for day in days]
        activity_profits = [profit_map.get(day, Decimal('0')) for day in days]
        deposit_area_path, deposit_line_path = self._line_path(activity_deposits)
        withdrawal_area_path, withdrawal_line_path = self._line_path(activity_withdrawals)
        profit_area_path, profit_line_path = self._line_path(activity_profits)

        balance_total = sum(
            (
                wallet.main_balance if wallet else Decimal('0'),
                wallet.bonus_balance if wallet else Decimal('0'),
                wallet.profit_balance if wallet else Decimal('0'),
            ),
            start=Decimal('0'),
        )
        balance_segments = []
        for label, value, tone in [
            ('Main', wallet.main_balance if wallet else Decimal('0'), 'info'),
            ('Profit', wallet.profit_balance if wallet else Decimal('0'), 'success'),
        ]:
            percent = 0 if balance_total == 0 else round((value / balance_total) * 100)
            balance_segments.append({'label': label, 'value': value, 'tone': tone, 'percent': percent})

        plan_total = sum((row['total'] or Decimal('0') for row in plan_allocation_qs), start=Decimal('0'))
        plan_allocation = []
        for row in plan_allocation_qs:
            value = row['total'] or Decimal('0')
            percent = 0 if plan_total == 0 else round((value / plan_total) * 100)
            plan_allocation.append({'label': row['plan__name'] or 'Plan', 'value': value, 'percent': percent})

        balance_overview_note = (
            f"{bonus_balance} bonus and {wallet.profit_balance if wallet else Decimal('0')} profit are already included in your balance overview."
            if bonus_active
            else f"{wallet.profit_balance if wallet else Decimal('0')} profit is already included in your balance overview."
        )

        context.update(
            wallet=wallet,
            investments=recent_investments,
            total_invested=total_invested,
            total_earned=total_earned,
            active_investments_count=active_investments_count,
            total_balance=wallet.total_balance if wallet else Decimal('0'),
            bonus_balance=bonus_balance,
            profit_balance=wallet.profit_balance if wallet else Decimal('0'),
            withdrawable_balance=wallet.withdrawable_balance if wallet else Decimal('0'),
            bonus_active=bonus_active,
            bonus_balance_note=f"{bonus_balance} bonus included in your account balance." if bonus_active else '',
            balance_overview_note=balance_overview_note,
            next_maturity=next_maturity,
            next_maturity_days=(max((next_maturity.end_date - timezone.now()).days, 0) if next_maturity else None),
            chart_start_date=selected_start.isoformat(),
            chart_end_date=selected_end.isoformat(),
            chart_range_label=f"{selected_start.strftime('%b %d, %Y')} - {selected_end.strftime('%b %d, %Y')}",
            chart_heading=f"Activity: {selected_start.strftime('%b %d, %Y')} - {selected_end.strftime('%b %d, %Y')}",
            activity_days=activity_days,
            activity_axis_labels=activity_axis_labels,
            activity_series=[
                {
                    'label': 'Deposits',
                    'tone': 'success',
                    'total': sum(activity_deposits, Decimal('0')),
                    'area_path': deposit_area_path,
                    'line_path': deposit_line_path,
                },
                {
                    'label': 'Withdrawals',
                    'tone': 'danger',
                    'total': sum(activity_withdrawals, Decimal('0')),
                    'area_path': withdrawal_area_path,
                    'line_path': withdrawal_line_path,
                },
                {
                    'label': 'Profit',
                    'tone': 'info',
                    'total': sum(activity_profits, Decimal('0')),
                    'area_path': profit_area_path,
                    'line_path': profit_line_path,
                },
            ],
            balance_segments=balance_segments,
            plan_allocation=plan_allocation,
        )
        return context


class LandingView(TemplateView):
    template_name = 'landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plans = InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')
        context['featured_plans'] = plans[:4]
        context['plan_count'] = plans.count()
        context['bonus_amount'] = get_setting_decimal('WELCOME_BONUS', default='50')
        context['min_withdrawal_amount'] = get_setting_decimal('MIN_WITHDRAWAL_AMOUNT', default='10')
        context['currency'] = str(get_setting('CURRENCY', default='USD') or 'USD')
        context['welcome_copy'] = (
            f"Start with a configurable welcome bonus, then scale into live plans with a clear withdrawal floor."
        )
        return context


class PlanListView(ListView):
    template_name = 'plans.html'
    model = InvestmentPlan
    context_object_name = 'plans'
    paginate_by = 12

    def _base_template(self):
        return 'base.html' if self.request.user.is_authenticated else 'public_base.html'

    def get_queryset(self):
        return InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = self._base_template()
        context['plan_form'] = InvestmentPlanForm()
        context['can_invest'] = self.request.user.is_authenticated
        context['create_form'] = CreateInvestmentForm(user=self.request.user) if self.request.user.is_authenticated else None
        context['open_plan_modal'] = False
        context['open_investment_modal'] = False
        if self.request.user.is_authenticated:
            wallet = Wallet.objects.filter(
                user=self.request.user,
                wallet_type__in=['primary', 'trading'],
                is_active=True,
            ).order_by('-is_default', 'created_at').first()
            if wallet and context['create_form']:
                context['create_form'].fields['amount'].widget.attrs['data-available'] = str(wallet.total_balance)
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "You do not have permission to add plans.")
            return redirect('plans')

        form = InvestmentPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan created successfully.")
            return redirect('plans')

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        context['plan_form'] = form
        context['open_plan_modal'] = True
        return self.render_to_response(context)


class InvestmentListView(LoginRequiredMixin, ListView):
    template_name = 'my_investments.html'
    model = UserInvestment
    context_object_name = 'investments'
    paginate_by = 10

    def get_queryset(self):
        return UserInvestment.objects.filter(user=self.request.user).order_by('-start_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = CreateInvestmentForm(user=self.request.user)
        context['open_investment_modal'] = False
        wallet = Wallet.objects.filter(
            user=self.request.user,
            wallet_type__in=['primary', 'trading'],
            is_active=True,
        ).order_by('-is_default', 'created_at').first()
        if wallet:
            context['create_form'].fields['amount'].widget.attrs['data-available'] = str(wallet.total_balance)
        context['investments'] = attach_profit_schedule(context.get('investments', []), max_rows=None)
        return context


class CreateInvestmentView(LoginRequiredMixin, FormView):
    template_name = 'my_investments.html'
    form_class = CreateInvestmentForm
    success_url = reverse_lazy('my_investments')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        plan = form.cleaned_data['plan']
        amount = form.cleaned_data['amount']
        wallet = form.cleaned_data.get('wallet')
        try:
            create_investment(
                self.request.user,
                plan,
                amount,
                wallet=wallet,
                risk_acknowledged=form.cleaned_data.get('risk_acknowledged', False),
            )
            messages.success(self.request, "Investment created successfully.")
            create_notification(
                self.request.user,
                "Investment created",
                f"Your investment of {amount} in {plan.name} was created successfully.",
                level='success',
            )
            next_url = self.request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return super().form_valid(form)
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)

    def form_invalid(self, form):
        next_url = self.request.POST.get('next')
        if next_url and 'plans' in next_url:
            plans = InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')
            context = {
                'plans': plans,
                'plan_form': InvestmentPlanForm(),
                'create_form': form,
                'open_plan_modal': False,
                'open_investment_modal': True,
                'base_template': self._base_template(),
                'can_invest': self.request.user.is_authenticated,
            }
            return self.render_to_response(context, template_name='plans.html')

        investments = attach_profit_schedule(
            UserInvestment.objects.filter(user=self.request.user).order_by('-start_date'),
            max_rows=None,
        )
        context = self.get_context_data(form=form)
        context['investments'] = investments
        context['create_form'] = form
        context['open_investment_modal'] = True
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['investments'] = attach_profit_schedule(
            UserInvestment.objects.filter(user=self.request.user).order_by('-start_date'),
            max_rows=None,
        )
        context['create_form'] = context.get('form', CreateInvestmentForm(user=self.request.user))
        context['open_investment_modal'] = False
        wallet = Wallet.objects.filter(
            user=self.request.user,
            wallet_type__in=['primary', 'trading'],
            is_active=True,
        ).order_by('-is_default', 'created_at').first()
        if wallet and context.get('create_form'):
            context['create_form'].fields['amount'].widget.attrs['data-available'] = str(wallet.total_balance)
        return context

# Create your views here.
