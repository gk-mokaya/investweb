from decimal import Decimal
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.core.cache import cache
from datetime import timedelta
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

from investments.forms import CreateInvestmentForm, InvestmentPlanForm
from investments.models import BonusTracker, InvestmentPlan, UserInvestment, DailyProfit
from investments.services import create_investment
from accounts.services import create_notification
from wallets.models import Wallet
from wallets.services import get_primary_wallet


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

    def _build_points(self, series, width, height, padding):
        if not series:
            mid_y = round(height / 2)
            return {
                'line': f"{padding},{mid_y} {width - padding},{mid_y}",
                'area': f"{padding},{height - padding} {padding},{mid_y} {width - padding},{mid_y} {width - padding},{height - padding}",
            }
        max_v = max(series)
        min_v = min(series)
        span = max_v - min_v
        if span == 0:
            span = 1
        step = (width - 2 * padding) / (len(series) - 1 or 1)
        points = []
        for idx, value in enumerate(series):
            x = padding + idx * step
            y = height - padding - ((value - min_v) / span) * (height - 2 * padding)
            points.append(f"{round(x, 2)},{round(y, 2)}")
        line = " ".join(points)
        area = f"{padding},{height - padding} {line} {width - padding},{height - padding}"
        return {'line': line, 'area': area}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cache_key = f"dashboard_totals_{self.request.user.id}"
        cached = cache.get(cache_key)

        wallet = get_primary_wallet(self.request.user)
        investments_qs = UserInvestment.objects.filter(user=self.request.user).order_by('-start_date')
        bonus = BonusTracker.objects.filter(user=self.request.user).first()

        if cached:
            total_invested = cached['total_invested']
            total_earned = cached['total_earned']
            allocation = cached['allocation']
            profit_series = cached['profit_series']
            profit_labels = cached['profit_labels']
            profit_pairs = cached.get('profit_pairs', list(zip(profit_labels, profit_series)))
            profit_points = cached.get('profit_points', [])
            line_points = cached.get('line_points', {})
            sparkline_points = cached.get('sparkline_points', {})
        else:
            total_invested = investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            total_earned = investments_qs.aggregate(total=Sum('total_earned'))['total'] or Decimal('0')

            allocation_queryset = (
                investments_qs.values('plan__name')
                .annotate(total=Sum('amount'))
                .order_by('-total')
            )
            allocation = []
            for row in allocation_queryset:
                percent = (row['total'] / total_invested * 100) if total_invested else 0
                allocation.append({'name': row['plan__name'], 'total': row['total'], 'percent': round(percent, 2)})

            today = timezone.now().date()
            start_date = today - timedelta(days=6)
            profits = (
                DailyProfit.objects.filter(investment__user=self.request.user, date__gte=start_date)
                .values('date')
                .annotate(total=Sum('amount'))
                .order_by('date')
            )
            profit_map = {row['date']: row['total'] for row in profits}
            profit_labels = []
            profit_series = []
            profit_points = []
            for i in range(7):
                day = start_date + timedelta(days=i)
                profit_labels.append(day.strftime('%b %d'))
                profit_series.append(float(profit_map.get(day, 0)))
            max_profit = max(profit_series) if profit_series else 0
            for label, value in zip(profit_labels, profit_series):
                height = int((value / max_profit) * 100) if max_profit else 0
                profit_points.append({'label': label, 'value': value, 'height': height})
            profit_pairs = list(zip(profit_labels, profit_series))
            line_points = self._build_points(profit_series, width=320, height=180, padding=14)
            sparkline_points = self._build_points(profit_series, width=90, height=28, padding=4)

            cache.set(
                cache_key,
                {
                    'total_invested': total_invested,
                    'total_earned': total_earned,
                    'allocation': allocation,
                    'profit_series': profit_series,
                    'profit_labels': profit_labels,
                    'profit_pairs': profit_pairs,
                    'profit_points': profit_points,
                    'line_points': line_points,
                    'sparkline_points': sparkline_points,
                },
                60,
            )
        context.update(
            wallet=wallet,
            investments=attach_profit_schedule(investments_qs[:5], max_rows=30),
            total_invested=total_invested,
            total_earned=total_earned,
            bonus=bonus,
            today=timezone.now(),
            allocation=allocation,
            profit_series=profit_series,
            profit_labels=profit_labels,
            profit_pairs=profit_pairs,
            profit_points=profit_points,
            line_points=line_points,
            sparkline_points=sparkline_points,
        )
        return context


class PlanListView(LoginRequiredMixin, ListView):
    template_name = 'plans.html'
    model = InvestmentPlan
    context_object_name = 'plans'
    paginate_by = 12

    def get_queryset(self):
        return InvestmentPlan.objects.filter(is_active=True).order_by('min_amount')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plan_form'] = InvestmentPlanForm()
        context['create_form'] = CreateInvestmentForm(user=self.request.user)
        context['open_plan_modal'] = False
        context['open_investment_modal'] = False
        wallet = Wallet.objects.filter(
            user=self.request.user,
            wallet_type__in=['primary', 'trading'],
            is_active=True,
        ).order_by('-is_default', 'created_at').first()
        if wallet:
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
                auto_reinvest=form.cleaned_data.get('auto_reinvest', False),
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
