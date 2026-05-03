from decimal import Decimal

from django.test import TestCase

from settingsconfig.models import SystemSetting
from settingsconfig.utils import get_setting_decimal


class SettingUtilsTests(TestCase):
    def test_get_setting_decimal_falls_back_for_invalid_values(self):
        SystemSetting.objects.update_or_create(key='WELCOME_BONUS', defaults={'value': 'not-a-number'})

        self.assertEqual(get_setting_decimal('WELCOME_BONUS', default='50'), Decimal('50'))
