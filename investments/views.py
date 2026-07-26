from decimal import Decimal
from collections import defaultdict
from decimal import Decimal
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView
from django.db.models.functions import TruncDate

from investments.forms import CreateInvestmentForm, InvestmentPlanForm
from investments.models import InvestmentPlan, UserInvestment, DailyProfit
from investments.services import create_investment
from accounts.services import create_notification
from deposits.models import Deposit
from wallets.models import Wallet
from wallets.services import get_primary_wallet
from investments.services import get_investment_account
from settingsconfig.utils import get_setting, get_setting_decimal
from withdrawals.models import Withdrawal
from urllib.parse import urlencode


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

    @staticmethod
    def _sample_axis_labels(days, target=7):
        labels = [day.strftime('%b %d') for day in days]
        if len(labels) <= target:
            return labels
        if target <= 1:
            return [labels[-1]]
        indexes = sorted({round(index * (len(labels) - 1) / (target - 1)) for index in range(target)})
        return [labels[index] for index in indexes]

    @staticmethod
    def _color_cycle():
        return ['var(--primary)', 'var(--success)', 'var(--warning)', 'var(--danger)', 'var(--secondary)']

    @staticmethod
    def _polar_to_cartesian(cx, cy, radius, angle_deg):
        import math

        angle_rad = math.radians(angle_deg)
        return (
            cx + (radius * math.cos(angle_rad)),
            cy + (radius * math.sin(angle_rad)),
        )

    @classmethod
    def _pie_slice_path(cls, cx, cy, radius, start_percent, end_percent):
        if end_percent <= start_percent:
            return ''
        start_angle = (start_percent / 100.0) * 360.0 - 90.0
        end_angle = (end_percent / 100.0) * 360.0 - 90.0
        start_x, start_y = cls._polar_to_cartesian(cx, cy, radius, start_angle)
        end_x, end_y = cls._polar_to_cartesian(cx, cy, radius, end_angle)
        large_arc = 1 if (end_percent - start_percent) > 50 else 0
        return (
            f"M {cx:.2f},{cy:.2f} "
            f"L {start_x:.2f},{start_y:.2f} "
            f"A {radius:.2f},{radius:.2f} 0 {large_arc} 1 {end_x:.2f},{end_y:.2f} Z"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet = get_primary_wallet(self.request.user)
        investment_account = get_investment_account(self.request.user)
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

        selected_start = parse_date(raw_start) or (today - timedelta(days=13))
        selected_end = parse_date(raw_end) or today
        if selected_end < selected_start:
            selected_start, selected_end = selected_end, selected_start
        max_window = timedelta(days=90)
        if selected_end - selected_start > max_window:
            selected_end = selected_start + max_window
        days = [selected_start + timedelta(days=offset) for offset in range((selected_end - selected_start).days + 1)]
        date_window = (days[0], days[-1])
        chart_width = max(420, len(days) * 22)

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

        deposit_qs = Deposit.objects.filter(user=self.request.user, status='completed', completed_at__isnull=False)
        withdrawal_qs = Withdrawal.objects.filter(user=self.request.user, status__in=['approved', 'completed'])
        deposit_map = daily_amounts_datetime(deposit_qs, 'completed_at')
        withdrawal_map = daily_amounts_datetime(withdrawal_qs, 'created_at')
        activity_deposits = [deposit_map.get(day, Decimal('0')) for day in days]
        activity_withdrawals = [withdrawal_map.get(day, Decimal('0')) for day in days]
        deposit_area_path, deposit_line_path = self._line_path(activity_deposits)
        withdrawal_area_path, withdrawal_line_path = self._line_path(activity_withdrawals)
        active_investments = list(
            UserInvestment.objects.filter(user=self.request.user, status='active')
            .select_related('plan', 'wallet', 'account')
            .order_by('end_date')
        )
        investments_qs = UserInvestment.objects.filter(user=self.request.user).select_related('plan', 'wallet', 'account').order_by('-start_date')
        total_invested = investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_earned = investments_qs.aggregate(total=Sum('total_earned'))['total'] or Decimal('0')
        active_investments_count = len(active_investments)
        completed_positions_count = investment_account.completed_positions_count
        pending_deposits_count = Deposit.objects.filter(user=self.request.user, status__in=['pending', 'confirming']).count()
        pending_withdrawals_count = Withdrawal.objects.filter(user=self.request.user, status='pending').count()
        active_plans_count = InvestmentPlan.objects.filter(is_active=True).count()
        active_position_rows = []
        for investment in active_investments[:6]:
            duration_days = max((investment.end_date - investment.start_date).days, 1)
            elapsed_days = max((timezone.now() - investment.start_date).days, 0)
            progress = min(100, round((elapsed_days / duration_days) * 100))
            active_position_rows.append(
                {
                    'investment': investment,
                    'progress': progress,
                    'days_left': max((investment.end_date - timezone.now()).days, 0),
                    'earned': investment.total_earned,
                    'progress_value': max(progress, 1 if investment.total_earned > 0 else 0),
                }
            )

        primary_wallet_balance = wallet.total_balance if wallet else Decimal('0')
        investment_ledger_balance = investment_account.current_balance
        portfolio_total = primary_wallet_balance + investment_ledger_balance
        profit_by_plan = defaultdict(lambda: defaultdict(lambda: Decimal('0')))
        plan_invested = defaultdict(lambda: Decimal('0'))
        plan_position_counts = defaultdict(int)
        active_ids = [investment.id for investment in active_investments]
        profit_rows = DailyProfit.objects.filter(
            investment_id__in=active_ids,
            date__range=date_window,
        ).select_related('investment', 'investment__plan').order_by('date')
        for investment in active_investments:
            label = investment.effective_plan_name or investment.plan.name or 'Plan'
            plan_invested[label] += investment.amount or Decimal('0')
            plan_position_counts[label] += 1
        for profit in profit_rows:
            label = profit.investment.effective_plan_name or profit.investment.plan.name or 'Plan'
            profit_by_plan[label][profit.date] += profit.amount or Decimal('0')
        investment_series = []
        for index, (label, invested_total) in enumerate(sorted(plan_invested.items(), key=lambda item: item[1], reverse=True)):
            day_values = [profit_by_plan[label].get(day, Decimal('0')) for day in days]
            cumulative_values = []
            running_total = Decimal('0')
            for value in day_values:
                running_total += value
                cumulative_values.append(running_total)
            area_path, line_path = self._line_path(cumulative_values, width=chart_width)
            investment_series.append(
                {
                    'label': label,
                    'tone': ['info', 'success', 'warning', 'danger', 'secondary'][index % 5],
                    'total': running_total,
                    'invested': invested_total,
                    'positions': plan_position_counts[label],
                    'area_path': area_path,
                    'line_path': line_path,
                }
            )
        investment_chart_width = chart_width
        investment_axis_labels = self._sample_axis_labels(days)

        plan_allocation_qs = [
            {
                'label': label,
                'value': value,
                'positions': plan_position_counts[label],
            }
            for label, value in sorted(plan_invested.items(), key=lambda item: item[1], reverse=True)
        ]
        plan_total = sum((row['value'] or Decimal('0') for row in plan_allocation_qs), start=Decimal('0'))
        plan_allocation = []
        pie_colors = self._color_cycle()
        running_percent = 0
        for index, row in enumerate(plan_allocation_qs):
            value = row['value'] or Decimal('0')
            percent = 0 if plan_total == 0 else round((value / plan_total) * 100)
            color = pie_colors[index % len(pie_colors)]
            start = running_percent
            if index == len(plan_allocation_qs) - 1:
                end = 100
            else:
                end = min(100, running_percent + percent)
            running_percent = end
            slice_path = self._pie_slice_path(60, 60, 44, start, end)
            mid_percent = start + ((end - start) / 2)
            label_x, label_y = self._polar_to_cartesian(60, 60, 25, (mid_percent / 100.0) * 360.0 - 90.0)
            plan_allocation.append(
                {
                    'label': row['label'],
                    'value': value,
                    'percent': percent,
                    'investments': row['positions'],
                    'color': color,
                    'start': start,
                    'end': end,
                    'slice_path': slice_path,
                    'label_x': label_x,
                    'label_y': label_y,
                    'title': f"{row['label']} {percent}% {value}",
                }
            )
        cash_axis_labels = self._sample_axis_labels(days)

        context.update(
            wallet=wallet,
            investment_account=investment_account,
            investments=attach_profit_schedule(investments_qs, max_rows=None),
            total_invested=total_invested,
            total_earned=total_earned,
            active_investments_count=active_investments_count,
            portfolio_total=portfolio_total,
            primary_wallet_balance=primary_wallet_balance,
            investment_ledger_balance=investment_ledger_balance,
            withdrawable_balance=wallet.withdrawable_balance if wallet else Decimal('0'),
            active_plans_count=active_plans_count,
            pending_reviews_count=pending_deposits_count + pending_withdrawals_count,
            pending_deposits_count=pending_deposits_count,
            pending_withdrawals_count=pending_withdrawals_count,
            completed_positions_count=completed_positions_count,
            chart_start_date=selected_start.isoformat(),
            chart_end_date=selected_end.isoformat(),
            chart_range_label=f"{selected_start.strftime('%b %d, %Y')} - {selected_end.strftime('%b %d, %Y')}",
            cash_chart_heading='Cash movement',
            cash_chart_width=chart_width,
            cash_axis_labels=cash_axis_labels,
            cash_series=[
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
            ],
            investment_chart_heading='Investment performance',
            investment_chart_width=investment_chart_width,
            investment_axis_labels=investment_axis_labels,
            investment_series=investment_series,
            active_position_rows=active_position_rows,
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

    def get_template_names(self):
        if self.request.user.is_authenticated:
            return ['plans.html']
        return ['plans.html']

    def get_queryset(self):
        return InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = self._base_template()
        context['plan_form'] = InvestmentPlanForm()
        context['can_invest'] = self.request.user.is_authenticated
        context['is_authenticated_user'] = self.request.user.is_authenticated
        context['create_form'] = CreateInvestmentForm(user=self.request.user) if self.request.user.is_authenticated else None
        context['open_plan_modal'] = False
        context['open_investment_modal'] = False
        if self.request.user.is_authenticated:
            wallet = Wallet.objects.filter(
                user=self.request.user,
                wallet_type='primary',
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
        investments_qs = UserInvestment.objects.filter(user=self.request.user).order_by('-start_date')
        active_investments = investments_qs.filter(status='active')
        wallet = Wallet.objects.filter(
            user=self.request.user,
            wallet_type='primary',
            is_active=True,
        ).order_by('-is_default', 'created_at').first()
        investment_account = get_investment_account(self.request.user)
        primary_wallet_balance = wallet.total_balance if wallet else Decimal('0')
        investment_ledger_balance = investment_account.current_balance
        capital_mix_total = primary_wallet_balance + investment_ledger_balance
        context['create_form'] = CreateInvestmentForm(user=self.request.user)
        context['open_investment_modal'] = False
        context['investment_account'] = investment_account
        context['INVESTMENT_SUMMARY'] = investment_account
        context['total_invested'] = investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['total_earned'] = investments_qs.aggregate(total=Sum('total_earned'))['total'] or Decimal('0')
        context['active_investments_count'] = active_investments.count()
        context['next_maturity'] = active_investments.order_by('end_date').first()
        next_maturity = context['next_maturity']
        context['next_maturity_days'] = (max((next_maturity.end_date - timezone.now()).days, 0) if next_maturity else None)
        if wallet:
            context['create_form'].fields['amount'].widget.attrs['data-available'] = str(wallet.total_balance)
        context['investments'] = attach_profit_schedule(context.get('investments', []), max_rows=None)
        context['capital_mix_primary_balance'] = primary_wallet_balance
        context['capital_mix_investment_balance'] = investment_ledger_balance
        context['capital_mix_total'] = capital_mix_total
        context['capital_mix_primary_share'] = 0 if capital_mix_total == 0 else round((primary_wallet_balance / capital_mix_total) * 100)
        context['capital_mix_investment_share'] = 0 if capital_mix_total == 0 else round((investment_ledger_balance / capital_mix_total) * 100)
        return context


class CreateInvestmentView(LoginRequiredMixin, FormView):
    template_name = 'my_investments.html'
    form_class = CreateInvestmentForm
    success_url = reverse_lazy('my_investments')

    def _base_template(self):
        return 'base.html' if self.request.user.is_authenticated else 'public_base.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        plan = form.cleaned_data['plan']
        amount = form.cleaned_data['amount']
        wallet = form.cleaned_data.get('wallet')
        try:
            available_balance = wallet.total_balance if wallet else Decimal('0')
            if amount > available_balance:
                shortfall = amount - available_balance
                messages.info(
                    self.request,
                    f"Your selected wallet has a shortfall of {shortfall}. Continue to deposit to complete the investment request.",
                )
                deposit_url = reverse_lazy('deposit_list')
                query = urlencode(
                    {
                        'open_deposit_modal': '1',
                        'source': 'investment',
                        'minimum_amount': str(shortfall),
                        'investment_plan': str(plan.id),
                        'investment_amount': str(amount),
                        'investment_wallet': str(wallet.id) if wallet else '',
                        'deposit_step': '1',
                        'return_to': self.request.POST.get('next') or self.request.path,
                    }
                )
                return redirect(f"{deposit_url}?{query}")

            create_investment(
                self.request.user,
                plan,
                amount,
                wallet=wallet,
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
            return render(self.request, 'plans.html', context)

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
        investments_qs = UserInvestment.objects.filter(user=self.request.user).order_by('-start_date')
        active_investments = investments_qs.filter(status='active')
        wallet = Wallet.objects.filter(
            user=self.request.user,
            wallet_type='primary',
            is_active=True,
        ).order_by('-is_default', 'created_at').first()
        investment_account = get_investment_account(self.request.user)
        primary_wallet_balance = wallet.total_balance if wallet else Decimal('0')
        investment_ledger_balance = investment_account.current_balance
        capital_mix_total = primary_wallet_balance + investment_ledger_balance
        context['investment_account'] = investment_account
        context['INVESTMENT_SUMMARY'] = investment_account
        context['investments'] = attach_profit_schedule(investments_qs, max_rows=None)
        context['total_invested'] = investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['total_earned'] = investments_qs.aggregate(total=Sum('total_earned'))['total'] or Decimal('0')
        context['active_investments_count'] = active_investments.count()
        context['next_maturity'] = active_investments.order_by('end_date').first()
        next_maturity = context['next_maturity']
        context['next_maturity_days'] = (max((next_maturity.end_date - timezone.now()).days, 0) if next_maturity else None)
        context['create_form'] = context.get('form', CreateInvestmentForm(user=self.request.user))
        context['open_investment_modal'] = False
        if wallet and context.get('create_form'):
            context['create_form'].fields['amount'].widget.attrs['data-available'] = str(wallet.total_balance)
        context['capital_mix_primary_balance'] = primary_wallet_balance
        context['capital_mix_investment_balance'] = investment_ledger_balance
        context['capital_mix_total'] = capital_mix_total
        context['capital_mix_primary_share'] = 0 if capital_mix_total == 0 else round((primary_wallet_balance / capital_mix_total) * 100)
        context['capital_mix_investment_share'] = 0 if capital_mix_total == 0 else round((investment_ledger_balance / capital_mix_total) * 100)
        return context

# Create your views here.
