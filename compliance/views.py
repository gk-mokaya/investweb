from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.views.generic import ListView, TemplateView

from adminpanel.models import AuditLog
from accounts.models import LoginLog
from django.contrib.auth.models import User
from kyc.models import KYCProfile
from withdrawals.models import Withdrawal


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class AuditLogListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'audit_logs.html'
    model = AuditLog
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        return AuditLog.objects.select_related('actor').order_by('-created_at')


class AuditLogExportView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    def get(self, request):
        logs = AuditLog.objects.select_related('actor').order_by('-created_at')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        response.write("timestamp,actor,action,entity,entity_id,meta\n")
        for log in logs:
            response.write(
                f"{log.created_at},{log.actor.username if log.actor else ''},{log.action},{log.target_type},{log.target_id},{log.meta}\n"
            )
        return response


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
                    reasons.append('Withdrawals pending without verified KYC')
            ip_count = LoginLog.objects.filter(user=user).values('ip_address').distinct().count()
            if ip_count >= 4:
                reasons.append('Multiple IP logins detected')
            if reasons:
                risky_users.append({'user': user, 'reasons': reasons})
        context['risky_users'] = risky_users
        return context

