from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils import timezone

from settingsconfig.mail import send_system_email
from settingsconfig.utils import get_setting


def _build_unique_username(email: str) -> str:
    base = (email.split('@')[0] or 'user').lower()
    base = ''.join(ch for ch in base if ch.isalnum() or ch in {'_', '-', '.'})
    base = base[:25] or 'user'
    candidate = base
    index = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{index}"
        index += 1
    return candidate


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = "Email address"

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = _build_unique_username(user.email)
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email address", widget=forms.EmailInput(attrs={'autofocus': True}))

    error_messages = {
        'invalid_login': "Please enter a valid email and password.",
        'inactive': "This account is inactive.",
    }

    def clean(self):
        email = (self.cleaned_data.get('username') or '').strip().lower()
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise self.get_invalid_login_error()

            self.user_cache = authenticate(self.request, username=user.username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class BrandedPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(label="Email address")

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError("No account was found with that email address.")
        return email

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        project_name = get_setting('PROJECT_NAME', default='Invest Platform')
        support_email = get_setting('SUPPORT_EMAIL', default='')
        context['project_name'] = project_name
        context['support_email'] = support_email
        context['request_time'] = timezone.now()

        subject = render_to_string(subject_template_name, context).replace('\n', '').replace('\r', '')
        text_body = render_to_string(email_template_name, context)
        html_body = render_to_string(html_email_template_name, context) if html_email_template_name else None
        send_system_email(subject=subject, body_text=text_body, body_html=html_body, recipients=[to_email])


class BrandedSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

