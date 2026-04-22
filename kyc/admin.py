from django.contrib import admin
from kyc.models import KYCProfile


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'country', 'id_type', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'country', 'id_type')
    search_fields = ('user__username', 'full_name', 'id_number')

# Register your models here.
