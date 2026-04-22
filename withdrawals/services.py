from __future__ import annotations

from typing import Any

from django.utils import timezone
from settingsconfig.utils import get_setting

from withdrawals.models import Withdrawal


class ProviderError(Exception):
    pass


def process_automated_withdrawal(withdrawal: Withdrawal) -> dict[str, Any]:
    provider = str(get_setting('CRYPTO_PAYOUT_PROVIDER', default='manual')).lower()
    if provider in {'', 'manual'}:
        raise ProviderError("Automated payouts are not configured.")

    # Placeholder for provider integrations (e.g., NOWPayments)
    # Implement provider-specific API call here.
    raise ProviderError(f"Provider '{provider}' not implemented.")


def mark_withdrawal_completed(withdrawal: Withdrawal) -> None:
    withdrawal.status = 'completed'
    withdrawal.processed_at = timezone.now()
    withdrawal.save(update_fields=['status', 'processed_at'])
