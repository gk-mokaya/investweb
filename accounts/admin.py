from django.contrib import admin
from accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_new_user', 'has_withdrawn', 'created_at')
    search_fields = ('user__username', 'user__email')

# Register your models here.
