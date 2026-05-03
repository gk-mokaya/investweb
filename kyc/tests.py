from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from kyc.forms import KYCForm
from kyc.models import KYCProfile


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
