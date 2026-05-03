from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils.encoding import force_bytes
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from accounts.models import LoginLog, UserProfile
from accounts.services import create_notification
from adminpanel.utils import log_action
from kyc.models import KYCProfile
from settingsconfig.mail import send_system_email
from settingsconfig.utils import get_setting
from users.forms import AdminUserCreateForm, AdminUserForm, UserProfileAdminForm


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class UserAdminListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'admin_users.html'
    model = User
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        queryset = User.objects.select_related('userprofile').order_by('-date_joined')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        if status == 'staff':
            queryset = queryset.filter(is_staff=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif status == 'active':
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status'] = self.request.GET.get('status', '').strip()
        context['q'] = self.request.GET.get('q', '').strip()
        context['total_users'] = User.objects.count()
        context['staff_users'] = User.objects.filter(is_staff=True).count()
        context['inactive_users'] = User.objects.filter(is_active=False).count()
        return context


def send_admin_password_reset(request, user_obj):
    if not user_obj.email:
        return False
    protocol = 'https' if request.is_secure() else 'http'
    domain = request.get_host()
    uid = urlsafe_base64_encode(force_bytes(user_obj.pk))
    token = default_token_generator.make_token(user_obj)
    context = {
        'user': user_obj,
        'uid': uid,
        'token': token,
        'protocol': protocol,
        'domain': domain,
        'project_name': get_setting('PROJECT_NAME', default='Invest Platform'),
        'support_email': get_setting('SUPPORT_EMAIL', default=''),
    }
    subject = render_to_string('emails/password_reset_subject.txt', context).replace('\n', '').replace('\r', '')
    text_body = render_to_string('emails/password_reset_email.txt', context)
    html_body = render_to_string('emails/password_reset_email.html', context)
    send_system_email(subject=subject, body_text=text_body, body_html=html_body, recipients=[user_obj.email])
    return True


class UserAdminDetailView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'admin_user_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = get_object_or_404(User.objects.select_related('userprofile'), pk=self.kwargs['pk'])
        profile, _ = UserProfile.objects.get_or_create(user=user_obj)
        context['target_user'] = user_obj
        context['user_form'] = AdminUserForm(instance=user_obj)
        context['profile_form'] = UserProfileAdminForm(instance=profile)
        context['kyc_profile'] = KYCProfile.objects.filter(user=user_obj).first()
        context['login_logs'] = LoginLog.objects.filter(user=user_obj).order_by('-created_at')[:10]
        return context


class UserAdminCreateView(LoginRequiredMixin, StaffOnlyMixin, FormView):
    template_name = 'admin_user_create.html'
    form_class = AdminUserCreateForm

    def form_valid(self, form):
        user_obj = form.save(commit=False)
        user_obj.email = (user_obj.email or '').strip().lower()
        user_obj.set_unusable_password()
        user_obj.save()
        UserProfile.objects.get_or_create(user=user_obj)

        sent_reset = False
        if form.cleaned_data.get('send_reset_link'):
            sent_reset = send_admin_password_reset(self.request, user_obj)

        log_action(self.request.user, 'user_created', 'user', user_obj.id, {'username': user_obj.username, 'email': user_obj.email})
        messages.success(self.request, 'User created successfully.')
        if sent_reset:
            messages.success(self.request, 'A password reset link was sent to the user email.')
        elif form.cleaned_data.get('send_reset_link'):
            messages.warning(self.request, 'The reset link was not sent because the account has no email address.')
        return redirect('admin_user_detail', pk=user_obj.pk)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form), status=400)


class UserAdminUpdateView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        profile, _ = UserProfile.objects.get_or_create(user=user_obj)
        user_form = AdminUserForm(request.POST, instance=user_obj)
        profile_form = UserProfileAdminForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            log_action(request.user, 'user_updated', 'user', user_obj.id, {'username': user_obj.username})
            messages.success(request, 'User updated successfully.')
            return redirect('admin_user_detail', pk=user_obj.pk)
        context = {
            'target_user': user_obj,
            'user_form': user_form,
            'profile_form': profile_form,
            'kyc_profile': KYCProfile.objects.filter(user=user_obj).first(),
            'login_logs': LoginLog.objects.filter(user=user_obj).order_by('-created_at')[:10],
        }
        return render(request, 'admin_user_detail.html', context)


class UserToggleActiveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        user_obj.is_active = not user_obj.is_active
        user_obj.save(update_fields=['is_active'])
        log_action(request.user, 'user_status_changed', 'user', user_obj.id, {'is_active': user_obj.is_active})
        messages.success(request, f"User {'activated' if user_obj.is_active else 'deactivated'}.")
        return redirect(request.META.get('HTTP_REFERER') or reverse_lazy('admin_user_detail', kwargs={'pk': user_obj.pk}))


class UserToggleStaffView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        user_obj.is_staff = not user_obj.is_staff
        user_obj.save(update_fields=['is_staff'])
        log_action(request.user, 'user_role_changed', 'user', user_obj.id, {'is_staff': user_obj.is_staff})
        messages.success(request, f"Staff access {'enabled' if user_obj.is_staff else 'removed'}.")
        return redirect(request.META.get('HTTP_REFERER') or reverse_lazy('admin_user_detail', kwargs={'pk': user_obj.pk}))


class UserSendResetLinkView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        if not user_obj.email:
            messages.error(request, 'This user does not have an email address yet.')
            return redirect(request.META.get('HTTP_REFERER') or reverse_lazy('admin_user_detail', kwargs={'pk': user_obj.pk}))
        send_admin_password_reset(request, user_obj)
        log_action(request.user, 'user_password_reset_sent', 'user', user_obj.id, {'username': user_obj.username, 'email': user_obj.email})
        messages.success(request, 'Password reset link sent to the user email.')
        return redirect(request.META.get('HTTP_REFERER') or reverse_lazy('admin_user_detail', kwargs={'pk': user_obj.pk}))


class KYCReviewListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    template_name = 'kyc_reviews.html'
    model = KYCProfile
    context_object_name = 'kyc_profiles'
    paginate_by = 25

    def get_queryset(self):
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()
        queryset = KYCProfile.objects.select_related('user').order_by('-submitted_at')
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(full_name__icontains=query) | Q(id_number__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = KYCProfile.STATUS_CHOICES
        return context


class KYCApproveView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        profile.status = 'verified'
        profile.reviewed_at = timezone.now()
        profile.review_note = request.POST.get('review_note', '')
        profile.save(update_fields=['status', 'reviewed_at', 'review_note'])
        log_action(request.user, 'kyc_approved', 'kyc', profile.id, {'user': profile.user.username})
        messages.success(request, 'KYC approved.')
        return redirect(f"{reverse_lazy('admin_kyc_reviews')}?tab=kyc")


class KYCRejectView(LoginRequiredMixin, StaffOnlyMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        profile.status = 'rejected'
        profile.reviewed_at = timezone.now()
        profile.review_note = request.POST.get('review_note', '')
        profile.save(update_fields=['status', 'reviewed_at', 'review_note'])
        log_action(request.user, 'kyc_rejected', 'kyc', profile.id, {'user': profile.user.username})
        messages.error(request, 'KYC rejected.')
        return redirect(f"{reverse_lazy('admin_kyc_reviews')}?tab=kyc")


class KYCDownloadView(LoginRequiredMixin, StaffOnlyMixin, View):
    def get(self, request, pk):
        profile = get_object_or_404(KYCProfile, pk=pk)
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="kyc_{profile.user.username}_{profile.id}.txt"'
        response.write(f"User: {profile.user.username}\n")
        response.write(f"Status: {profile.get_status_display()}\n")
        response.write(f"Full name: {profile.full_name}\n")
        response.write(f"Date of birth: {profile.date_of_birth or ''}\n")
        response.write(f"Country: {profile.country}\n")
        response.write(f"Country of residence: {profile.country_of_residence}\n")
        response.write(f"ID type: {profile.get_id_type_display()}\n")
        response.write(f"ID number: {profile.id_number}\n")
        response.write(f"Submitted at: {profile.submitted_at or ''}\n")
        response.write(f"Reviewed at: {profile.reviewed_at or ''}\n")
        response.write(f"Review note: {profile.review_note}\n")
        return response
