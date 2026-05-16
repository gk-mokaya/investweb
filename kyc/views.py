from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView

from kyc.background import start_verification_background
from kyc.forms import KYCForm
from kyc.models import KYCProfile, KYCVerificationRun
from kyc.services import VERIFICATION_STAGES, create_verification_run, get_latest_verification_run


class KYCView(LoginRequiredMixin, FormView):
    template_name = 'kyc_verify.html'
    form_class = KYCForm

    def get_object(self):
        profile, _ = KYCProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kyc_profile'] = self.get_object()
        verification_run = get_latest_verification_run(context['kyc_profile'])
        context['kyc_verification_run'] = verification_run
        context['kyc_verification_stages'] = VERIFICATION_STAGES
        context['open_kyc_modal'] = False
        context['open_kyc_progress_modal'] = bool(verification_run and verification_run.status in {'queued', 'processing'})
        context['kyc_step'] = '1'
        context['form'] = KYCForm(instance=self.get_object(), step=context['kyc_step'])
        return context

    def post(self, request, *args, **kwargs):
        profile = self.get_object()
        step = request.POST.get('kyc_step', '1')
        form = self.form_class(request.POST, request.FILES, instance=profile, step=step)
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
                verification_run = create_verification_run(profile, actor=request.user)
                start_verification_background(verification_run.id)
                messages.success(request, "KYC submitted successfully. Automatic verification has started.")
                context = self.get_context_data()
                context['kyc_verification_run'] = verification_run
                context['kyc_verification_stages'] = VERIFICATION_STAGES
                context['open_kyc_progress_modal'] = True
                context['kyc_step'] = '3'
                context['form'] = KYCForm(instance=profile, step='3')
                return self.render_to_response(context)

            profile.save(update_fields=updated_fields)
            context = self.get_context_data()
            context['form'] = KYCForm(instance=profile, step=str(int(step) + 1))
            context['open_kyc_modal'] = True
            context['kyc_step'] = str(int(step) + 1)
            messages.success(request, "Section saved. Continue to the next step.")
            return self.render_to_response(context)

        context = self.get_context_data(form=form)
        context['open_kyc_modal'] = True
        context['kyc_step'] = step
        return self.render_to_response(context)


class KYCVerificationStatusView(LoginRequiredMixin, View):
    def get(self, request, run_id):
        run = get_object_or_404(KYCVerificationRun.objects.select_related('profile'), pk=run_id)
        if run.profile.user_id != request.user.id and not request.user.is_staff:
            return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)
        return JsonResponse({
            'ok': True,
            'run': {
                'id': run.id,
                'profile_id': run.profile_id,
                'status': run.status,
                'current_stage': run.current_stage,
                'stage_label': run.stage_label,
                'progress_percent': run.progress_percent,
                'risk_score': run.risk_score,
                'error_message': run.error_message,
                'stage_log': run.stage_log or [],
                'created_at': run.created_at.isoformat() if run.created_at else None,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
            },
            'stages': [{'key': stage.key, 'label': stage.label, 'percent': stage.percent} for stage in VERIFICATION_STAGES],
        })
