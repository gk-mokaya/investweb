from django.contrib import admin
from kyc.models import KYCProfile, KYCVerificationEvent, KYCVerificationRun


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'verification_method', 'country', 'id_type', 'submitted_at', 'reviewed_at', 'revoked_at')
    list_filter = ('status', 'verification_method', 'country', 'id_type')
    search_fields = ('user__username', 'full_name', 'id_number')


@admin.register(KYCVerificationRun)
class KYCVerificationRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'status', 'current_stage', 'progress_percent', 'risk_score', 'created_at', 'completed_at')
    list_filter = ('status', 'current_stage')
    search_fields = ('profile__user__username', 'profile__full_name')


@admin.register(KYCVerificationEvent)
class KYCVerificationEventAdmin(admin.ModelAdmin):
    list_display = ('run', 'stage_key', 'status', 'percent', 'created_at')
    list_filter = ('status', 'stage_key')
    search_fields = ('run__profile__user__username', 'message')

# Register your models here.
