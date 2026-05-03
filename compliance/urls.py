from django.urls import path

from compliance.views import AuditLogExportView, AuditLogListView, RiskDashboardView


urlpatterns = [
    path('audit-logs/', AuditLogListView.as_view(), name='admin_audit_logs'),
    path('audit-logs/export/', AuditLogExportView.as_view(), name='admin_audit_logs_export'),
    path('risk/', RiskDashboardView.as_view(), name='admin_risk_dashboard'),
]

