from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class KYCProfile(models.Model):
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    ID_TYPE_CHOICES = [
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver License'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_submitted')
    full_name = models.CharField(max_length=150, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=80, blank=True, default='')
    id_type = models.CharField(max_length=30, choices=ID_TYPE_CHOICES, blank=True, default='')
    id_number = models.CharField(max_length=60, blank=True, default='')
    address_line = models.CharField(max_length=200, blank=True, default='')
    city = models.CharField(max_length=80, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    phone_number = models.CharField(max_length=40, blank=True, default='')
    country_of_residence = models.CharField(max_length=80, blank=True, default='')
    source_of_funds = models.CharField(max_length=120, blank=True, default='')
    source_of_funds_other = models.CharField(max_length=120, blank=True, default='')
    tax_id = models.CharField(max_length=60, blank=True, default='')
    id_document_front = models.FileField(upload_to='kyc/', blank=True, null=True)
    id_document_back = models.FileField(upload_to='kyc/', blank=True, null=True)
    selfie_photo = models.FileField(upload_to='kyc/', blank=True, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default='')

    def __str__(self) -> str:
        return f"KYC {self.user.username} - {self.status}"

    def mark_submitted(self):
        self.status = 'pending'
        self.submitted_at = timezone.now()

    def completion_percent(self) -> int:
        fields = [
            self.full_name,
            self.date_of_birth,
            self.country,
            self.id_type,
            self.id_number,
            self.address_line,
            self.city,
            self.postal_code,
            self.phone_number,
            self.country_of_residence,
            self.source_of_funds,
            self.tax_id,
        ]
        if self.source_of_funds == 'other':
            fields.append(self.source_of_funds_other)
        total = len(fields) + 3
        filled = sum(1 for value in fields if value)
        filled += 1 if self.id_document_front else 0
        filled += 1 if self.id_document_back else 0
        filled += 1 if self.selfie_photo else 0
        if total == 0:
            return 0
        return int((filled / total) * 100)

    def missing_items(self) -> list[str]:
        missing = []
        if not self.full_name:
            missing.append('Full name')
        if not self.date_of_birth:
            missing.append('Date of birth')
        if not self.country:
            missing.append('Country')
        if not self.id_type:
            missing.append('ID type')
        if not self.id_number:
            missing.append('ID number')
        if not self.address_line:
            missing.append('Address')
        if not self.city:
            missing.append('City')
        if not self.postal_code:
            missing.append('Postal code')
        if not self.phone_number:
            missing.append('Phone number')
        if not self.country_of_residence:
            missing.append('Country of residence')
        if not self.source_of_funds:
            missing.append('Source of funds')
        if not self.tax_id:
            missing.append('Tax ID')
        if self.source_of_funds == 'other' and not self.source_of_funds_other:
            missing.append('Source of funds (other)')
        if not self.id_document_front:
            missing.append('ID front')
        if not self.id_document_back:
            missing.append('ID back')
        if not self.selfie_photo:
            missing.append('Selfie photo')
        return missing

# Create your models here.
