from decimal import Decimal, InvalidOperation
from typing import Any
import logging

from settingsconfig.models import SystemSetting


logger = logging.getLogger(__name__)


DEFAULT_SETTINGS: dict[str, Any] = {
    'PROJECT_NAME': 'Invest Platform',
    'SITE_TAGLINE': 'Investment Suite',
    'SITE_LOGO': '',
    'SITE_FAVICON': '',
    'SUPPORT_EMAIL': '',
    'SUPPORT_PHONE': '',
    'SUPPORT_ADDRESS': '',
    'WELCOME_BONUS': '50',
    'MIN_WITHDRAWAL_AMOUNT': '10',
    'CURRENCY': 'USD',
    'CRYPTO_PROVIDER': 'manual',
    'BLOCKCYPHER_TOKEN': '',
    'BLOCKCYPHER_CALLBACK_URL': '',
    'DESTINATION_BTC_ADDRESS': '',
    'DESTINATION_ETH_ADDRESS': '',
    'DESTINATION_USDT_ADDRESS': '',
    'GMAIL_CLIENT_ID': '',
    'GMAIL_CLIENT_SECRET': '',
    'GMAIL_REFRESH_TOKEN': '',
    'GMAIL_SENDER_EMAIL': '',
    'MANUAL_DEPOSIT_WALLET_ADDRESS': '',
}


def get_setting(key: str, default: Any | None = None) -> Any:
    try:
        setting = SystemSetting.objects.get(key=key)
        return setting.value
    except SystemSetting.DoesNotExist:
        return DEFAULT_SETTINGS.get(key, default)


def get_setting_decimal(key: str, default: str = '0') -> Decimal:
    value = get_setting(key, default=default)
    try:
        normalized = str(value).strip()
        if normalized == '':
            normalized = default
        return Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        logger.warning(
            "Invalid decimal setting for %s: %r. Falling back to default %r.",
            key,
            value,
            default,
        )
        return Decimal(str(default))
