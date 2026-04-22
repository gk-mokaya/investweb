from django import forms
from django.utils import timezone

from kyc.models import KYCProfile


class KYCForm(forms.ModelForm):
    STEP_FIELDS = {
        '1': [
            'full_name',
            'date_of_birth',
            'country',
            'phone_number',
            'source_of_funds',
            'source_of_funds_other',
        ],
        '2': [
            'address_line',
            'city',
            'postal_code',
            'country_of_residence',
            'tax_id',
        ],
        '3': [
            'id_type',
            'id_number',
            'id_document_front',
            'id_document_back',
            'selfie_photo',
        ],
    }

    SOURCE_CHOICES = [
        ('employed', 'Employed (Salary)'),
        ('business', 'Business Owner'),
        ('farmer', 'Farmer'),
        ('freelance', 'Freelance / Contract'),
        ('investments', 'Investments / Dividends'),
        ('rental', 'Rental Income'),
        ('pension', 'Pension'),
        ('student', 'Student / Scholarship'),
        ('family', 'Family Support'),
        ('other', 'Other'),
    ]

    class Meta:
        model = KYCProfile
        fields = (
            'full_name',
            'date_of_birth',
            'country',
            'id_type',
            'id_number',
            'address_line',
            'city',
            'postal_code',
            'phone_number',
            'country_of_residence',
            'source_of_funds',
            'source_of_funds_other',
            'tax_id',
            'id_document_front',
            'id_document_back',
            'selfie_photo',
        )

    def __init__(self, *args, **kwargs):
        step = kwargs.pop('step', None)
        super().__init__(*args, **kwargs)
        self.fields['date_of_birth'].widget.attrs.update({'type': 'date', 'class': 'date-input'})
        self.fields['source_of_funds'].widget = forms.Select(choices=self.SOURCE_CHOICES)
        required_fields = [
            'full_name',
            'date_of_birth',
            'country',
            'id_type',
            'id_number',
            'address_line',
            'city',
            'postal_code',
            'phone_number',
            'country_of_residence',
            'source_of_funds',
            'tax_id',
            'id_document_front',
            'id_document_back',
            'selfie_photo',
        ]
        for name in required_fields:
            if name in self.fields:
                self.fields[name].required = True
        self.fields['source_of_funds_other'].required = False
        self.fields['country_of_residence'].label = 'Country of residence'

        file_attrs = {
            'accept': 'image/*,application/pdf',
            'class': 'file-input',
            'data-preview': 'true',
        }
        self.fields['id_document_front'].widget = forms.FileInput(attrs=file_attrs)
        self.fields['id_document_back'].widget = forms.FileInput(attrs=file_attrs)
        selfie_attrs = {
            'accept': 'image/*',
            'capture': 'user',
            'class': 'file-input',
            'data-preview': 'true',
        }
        self.fields['selfie_photo'].widget = forms.FileInput(attrs=selfie_attrs)

        if step:
            step_fields = set(self.STEP_FIELDS.get(step, []))
            for name, field in self.fields.items():
                if name not in step_fields:
                    field.required = False

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if not dob:
            return dob
        today = timezone.now().date()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise forms.ValidationError("You must be at least 18 years old.")
        return dob

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get('source_of_funds')
        other = cleaned.get('source_of_funds_other')
        if source == 'other' and not other:
            self.add_error('source_of_funds_other', "Please specify your source of funds.")
        return cleaned

    def _validate_file(self, field_name: str, allowed_types: tuple[str, ...]):
        upload = self.cleaned_data.get(field_name)
        if not upload:
            return upload
        content_type = getattr(upload, 'content_type', '')
        name = getattr(upload, 'name', '').lower()
        if content_type and content_type not in allowed_types:
            raise forms.ValidationError("Unsupported file type.")
        if not content_type:
            if not any(name.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.pdf')):
                raise forms.ValidationError("Unsupported file type.")
        return upload

    def clean_id_document_front(self):
        return self._validate_file('id_document_front', ('image/jpeg', 'image/png', 'application/pdf'))

    def clean_id_document_back(self):
        return self._validate_file('id_document_back', ('image/jpeg', 'image/png', 'application/pdf'))

    def clean_selfie_photo(self):
        upload = self.cleaned_data.get('selfie_photo')
        if not upload:
            return upload
        content_type = getattr(upload, 'content_type', '')
        name = getattr(upload, 'name', '').lower()
        if content_type and content_type not in ('image/jpeg', 'image/png'):
            raise forms.ValidationError("Selfie must be a JPG or PNG image.")
        if not content_type and not (name.endswith('.jpg') or name.endswith('.jpeg') or name.endswith('.png')):
            raise forms.ValidationError("Selfie must be a JPG or PNG image.")
        return upload
