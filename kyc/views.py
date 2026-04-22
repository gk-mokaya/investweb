from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import FormView

from kyc.forms import KYCForm
from kyc.models import KYCProfile


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
        context['open_kyc_modal'] = False
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
                messages.success(request, "KYC submitted successfully. We'll review it shortly.")
                return redirect('kyc_verify')

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
