from datetime import date
import time

from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from kyc.background import start_verification_background
from kyc.forms import KYCForm
from kyc.models import KYCProfile, KYCVerificationRun
from kyc.services import create_verification_run


class KYCPolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass12345')
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='pass12345',
            is_staff=True,
        )

    def test_kyc_form_rejects_applicants_under_16(self):
        form = KYCForm(
            data={
                'full_name': 'Young User',
                'date_of_birth': date.today().replace(year=date.today().year - 15).isoformat(),
                'country': 'Kenya',
                'phone_number': '+254700000000',
                'source_of_funds': 'employed',
                'source_of_funds_other': '',
                'address_line': '123 Street',
                'city': 'Nairobi',
                'postal_code': '00100',
                'country_of_residence': 'Kenya',
                'tax_id': '123456',
                'id_type': 'national_id',
                'id_number': 'ABC123456',
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('at least 16 years old', form.errors['date_of_birth'][0].lower())

    def test_admin_rejects_underage_kyc_on_approval(self):
        profile = KYCProfile.objects.get(user=self.user)
        profile.status = 'pending'
        profile.full_name = 'Young User'
        profile.date_of_birth = date.today().replace(year=date.today().year - 15)
        profile.country = 'Kenya'
        profile.phone_number = '+254700000000'
        profile.source_of_funds = 'employed'
        profile.address_line = '123 Street'
        profile.city = 'Nairobi'
        profile.postal_code = '00100'
        profile.country_of_residence = 'Kenya'
        profile.tax_id = '123456'
        profile.id_type = 'national_id'
        profile.id_number = 'ABC123456'
        profile.save()

        client = Client()
        client.force_login(self.admin)

        response = client.post(reverse('admin_kyc_approve', args=[profile.id]), {'review_note': 'Approved'})
        self.assertEqual(response.status_code, 302)

        profile.refresh_from_db()
        self.assertEqual(profile.status, 'rejected')
        self.assertIn('under 16', profile.review_note.lower())

    def test_admin_can_revoke_automated_verification(self):
        profile = KYCProfile.objects.get(user=self.user)
        profile.status = 'verified'
        profile.verification_method = 'automated'
        profile.review_note = 'Auto verified by the system.'
        profile.reviewed_at = timezone.now()
        profile.save()

        client = Client()
        client.force_login(self.admin)

        response = client.post(reverse('admin_kyc_revoke', args=[profile.id]), {'review_note': 'Gap found in document review'})
        self.assertEqual(response.status_code, 302)

        profile.refresh_from_db()
        self.assertEqual(profile.status, 'pending')
        self.assertEqual(profile.verification_method, 'automated')
        self.assertIn('gap found', profile.revocation_note.lower())


class KYCAutomationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(username='tester-automation', email='tester2@example.com', password='pass12345')
        self.admin = User.objects.create_user(
            username='admin-automation',
            email='admin2@example.com',
            password='pass12345',
            is_staff=True,
        )

    def test_automatic_verification_completes_in_background(self):
        profile = KYCProfile.objects.get(user=self.user)
        profile.full_name = 'Tester User'
        profile.date_of_birth = date.today().replace(year=date.today().year - 25)
        profile.country = 'Kenya'
        profile.id_type = 'national_id'
        profile.id_number = 'ABC1234567'
        profile.address_line = '123 Street'
        profile.city = 'Nairobi'
        profile.postal_code = '00100'
        profile.phone_number = '+254700000000'
        profile.country_of_residence = 'Kenya'
        profile.source_of_funds = 'employed'
        profile.tax_id = '123456'
        profile.submitted_at = timezone.now()
        profile.status = 'pending'
        profile.id_document_front = SimpleUploadedFile('front.jpg', b'front-bytes', content_type='image/jpeg')
        profile.id_document_back = SimpleUploadedFile('back.jpg', b'back-bytes', content_type='image/jpeg')
        profile.selfie_photo = SimpleUploadedFile('selfie.jpg', b'selfie-bytes', content_type='image/jpeg')
        profile.save()

        run = create_verification_run(profile, actor=self.admin)
        start_verification_background(run.id)

        deadline = time.time() + 10
        while time.time() < deadline:
            profile.refresh_from_db()
            run.refresh_from_db()
            if run.status in {'verified', 'manual_review', 'rejected', 'failed'}:
                break
            time.sleep(0.2)

        profile.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(run.status, 'verified')
        self.assertEqual(profile.status, 'verified')
        self.assertEqual(profile.verification_method, 'automated')
        self.assertGreaterEqual(run.progress_percent, 100)
