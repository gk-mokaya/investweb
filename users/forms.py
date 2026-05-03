from django import forms
from django.contrib.auth.models import User

from accounts.models import UserProfile


class AdminUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser')


class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('is_new_user', 'has_withdrawn')


class AdminUserCreateForm(forms.ModelForm):
    send_reset_link = forms.BooleanField(required=False, initial=True, label='Send password reset link')

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['username'].help_text = 'Use a unique username for this account.'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
