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


class ProfileUpdateForm(forms.Form):
    first_name = forms.CharField(required=False, max_length=150)
    last_name = forms.CharField(required=False, max_length=150)
    phone_number = forms.CharField(required=False, max_length=40)
    country = forms.CharField(required=False, max_length=80)
    address_line = forms.CharField(required=False, max_length=200)
    city = forms.CharField(required=False, max_length=80)
    postal_code = forms.CharField(required=False, max_length=20)
    country_of_residence = forms.CharField(required=False, max_length=80)

    def __init__(self, *args, user=None, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.profile = profile
        self.fields['first_name'].widget.attrs.update({'placeholder': 'First name'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Last name'})
        self.fields['phone_number'].widget.attrs.update({'placeholder': 'Phone number'})
        self.fields['country'].widget.attrs.update({'placeholder': 'Country'})
        self.fields['address_line'].widget.attrs.update({'placeholder': 'Street address'})
        self.fields['city'].widget.attrs.update({'placeholder': 'City'})
        self.fields['postal_code'].widget.attrs.update({'placeholder': 'Postal code'})
        self.fields['country_of_residence'].widget.attrs.update({'placeholder': 'Country of residence'})
        if user:
            self.initial.setdefault('first_name', user.first_name)
            self.initial.setdefault('last_name', user.last_name)
        if profile:
            self.initial.setdefault('phone_number', profile.phone_number)
            self.initial.setdefault('country', profile.country)
            self.initial.setdefault('address_line', profile.address_line)
            self.initial.setdefault('city', profile.city)
            self.initial.setdefault('postal_code', profile.postal_code)
            self.initial.setdefault('country_of_residence', profile.country_of_residence)

    def save(self):
        if self.user is None or self.profile is None:
            raise ValueError("ProfileUpdateForm requires both user and profile.")

        self.user.first_name = self.cleaned_data.get('first_name', '')
        self.user.last_name = self.cleaned_data.get('last_name', '')
        self.user.save(update_fields=['first_name', 'last_name'])

        self.profile.phone_number = self.cleaned_data.get('phone_number', '')
        self.profile.country = self.cleaned_data.get('country', '')
        self.profile.address_line = self.cleaned_data.get('address_line', '')
        self.profile.city = self.cleaned_data.get('city', '')
        self.profile.postal_code = self.cleaned_data.get('postal_code', '')
        self.profile.country_of_residence = self.cleaned_data.get('country_of_residence', '')
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        self.profile.full_name = full_name
        self.profile.save(update_fields=[
            'phone_number',
            'country',
            'address_line',
            'city',
            'postal_code',
            'country_of_residence',
            'full_name',
        ])
        return self.user, self.profile


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
