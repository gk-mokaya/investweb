from django.contrib import admin
from adminpanel.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('actor__username', 'target_type', 'target_id')

# Register your models here.
