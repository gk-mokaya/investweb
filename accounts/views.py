from django.contrib.auth import login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView, ListView
from django.http import JsonResponse

from accounts.forms import (
    BrandedPasswordResetForm,
    BrandedSetPasswordForm,
    EmailAuthenticationForm,
    RegisterForm,
)
from accounts.models import Notification, LoginLog
from kyc.forms import KYCForm
from kyc.models import KYCProfile
from accounts.services import create_notification
from wallets.forms import WalletCreateForm, WalletTransferForm
from wallets.models import Wallet
from wallets.services import create_wallet, transfer_between_wallets
class RegisterView(FormView):
    template_name = 'auth_register.html'
    form_class = RegisterForm
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class UserLoginView(LoginView):
    template_name = 'auth_login.html'
    form_class = EmailAuthenticationForm


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('login')
    http_method_names = ['get', 'post', 'options']

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return redirect(self.next_page)


class UserPasswordResetView(PasswordResetView):
    template_name = 'auth_password_reset.html'
    email_template_name = 'emails/password_reset_email.txt'
    html_email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    form_class = BrandedPasswordResetForm


class UserPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'auth_password_reset_done.html'


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'auth_password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    form_class = BrandedSetPasswordForm


class UserPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'auth_password_reset_complete.html'


class ProfileView(TemplateView):
    template_name = 'profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = KYCProfile.objects.get_or_create(user=self.request.user)
        context['kyc_profile'] = profile
        context['open_kyc_modal'] = False
        context['kyc_step'] = '1'
        context['kyc_form'] = KYCForm(instance=profile, step=context['kyc_step'])
        context['form'] = context['kyc_form']
        context['login_logs'] = LoginLog.objects.filter(user=self.request.user).order_by('-created_at')[:5]
        context['wallets'] = Wallet.objects.filter(user=self.request.user).order_by('-is_default', 'created_at')
        context['wallet_create_form'] = WalletCreateForm()
        context['wallet_transfer_form'] = WalletTransferForm(user=self.request.user)
        context['open_wallet_create_modal'] = False
        context['open_wallet_transfer_modal'] = False
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'kyc_submit')

        if action == 'wallet_create':
            form = WalletCreateForm(request.POST)
            if form.is_valid():
                name = form.cleaned_data.get('name') or ''
                wallet_type = form.cleaned_data.get('wallet_type')
                existing = Wallet.objects.filter(user=request.user).count()
                wallet_name = name or f"Wallet {existing + 1}"
                create_wallet(
                    request.user,
                    name=wallet_name,
                    wallet_type=wallet_type,
                    is_active=True,
                )
                messages.success(request, "Wallet created successfully.")
                return redirect('profile')
            context = self.get_context_data()
            context['wallet_create_form'] = form
            context['open_wallet_create_modal'] = True
            return self.render_to_response(context)

        if action == 'wallet_transfer':
            form = WalletTransferForm(request.POST, user=request.user)
            if form.is_valid():
                try:
                    transfer_between_wallets(
                        from_wallet=form.cleaned_data['from_wallet'],
                        to_wallet=form.cleaned_data['to_wallet'],
                        amount=form.cleaned_data['amount'],
                        note=form.cleaned_data.get('note', ''),
                    )
                    messages.success(request, "Transfer completed.")
                    return redirect('profile')
                except ValueError as exc:
                    form.add_error(None, str(exc))
            context = self.get_context_data()
            context['wallet_transfer_form'] = form
            context['open_wallet_transfer_modal'] = True
            return self.render_to_response(context)

        profile, _ = KYCProfile.objects.get_or_create(user=request.user)
        step = request.POST.get('kyc_step', '1')
        form = KYCForm(request.POST, request.FILES, instance=profile, step=step)
        if form.is_valid():
            updated_fields = []
            step_fields = KYCForm.STEP_FIELDS.get(step, [])
            for field in step_fields:
                if field in form.cleaned_data:
                    setattr(profile, field, form.cleaned_data[field])
                    updated_fields.append(field)
            if step == '3':
                profile.mark_submitted()
                updated_fields.extend(['status', 'submitted_at'])
                profile.save(update_fields=updated_fields)
                messages.success(request, "KYC submitted successfully. We'll review it shortly.")
                create_notification(
                    request.user,
                    "KYC submitted",
                    "Your verification documents are under review.",
                    level='info',
                )
                return self.get(request, *args, **kwargs)

            profile.save(update_fields=updated_fields)
            context = self.get_context_data()
            context['kyc_form'] = KYCForm(instance=profile, step=str(int(step) + 1))
            context['form'] = context['kyc_form']
            context['open_kyc_modal'] = True
            context['kyc_step'] = str(int(step) + 1)
            messages.success(request, "Section saved. Continue to the next step.")
            return self.render_to_response(context)

        context = self.get_context_data()
        context['kyc_form'] = form
        context['form'] = form
        context['open_kyc_modal'] = True
        context['kyc_step'] = step
        return self.render_to_response(context)


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = 'notifications.html'
    model = Notification
    context_object_name = 'notifications'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        return redirect('dashboard')

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification_id = request.POST.get('notification_id')
        if not notification_id:
            return JsonResponse({'ok': False, 'error': 'Missing notification_id'}, status=400)

        updated = Notification.objects.filter(
            user=request.user,
            id=notification_id,
            is_read=False,
        ).update(is_read=True)
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'ok': True, 'updated': bool(updated), 'unread': unread})


class NotificationReadAllView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True, 'updated': updated, 'unread': 0})

# Create your views here.
