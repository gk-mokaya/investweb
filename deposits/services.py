from __future__ import annotations

from decimal import Decimal
from typing import Any

import requests

from deposits.models import Deposit
from payments.models import CryptoCurrency
from django.utils import timezone
from datetime import timedelta
from settingsconfig.utils import get_setting


class ProviderError(Exception):
    pass


def _blockcypher_base(symbol: str) -> str:
    if symbol == 'BTC':
        return 'https://api.blockcypher.com/v1/btc/main'
    if symbol == 'USDT':
        return 'https://api.blockcypher.com/v1/eth/main'
    return 'https://api.blockcypher.com/v1/eth/main'


def _blockcypher_destination(symbol: str) -> str:
    if symbol == 'BTC':
        return str(get_setting('DESTINATION_BTC_ADDRESS', default='')).strip()
    if symbol == 'USDT':
        return str(get_setting('DESTINATION_USDT_ADDRESS', default='')).strip()
    return str(get_setting('DESTINATION_ETH_ADDRESS', default='')).strip()


def create_automated_payment(crypto: CryptoCurrency) -> dict[str, Any] | None:
    provider = str(get_setting('CRYPTO_PROVIDER', default='manual')).lower()
    if provider != 'blockcypher':
        return None
    if crypto.symbol == 'USDT':
        return None

    token = str(get_setting('BLOCKCYPHER_TOKEN', default='')).strip()
    destination = _blockcypher_destination(crypto.symbol)
    callback_url = str(get_setting('BLOCKCYPHER_CALLBACK_URL', default='')).strip()

    if not token or not destination:
        return None

    base_url = _blockcypher_base(crypto.symbol)
    if crypto.symbol == 'BTC':
        endpoint = f"{base_url}/forwards?token={token}"
        payload = {'destination': destination}
    else:
        endpoint = f"{base_url}/payments?token={token}"
        payload = {'destination': destination}

    if callback_url:
        payload['callback_url'] = callback_url

    try:
        response = requests.post(endpoint, json=payload, timeout=20)
    except requests.RequestException as exc:
        raise ProviderError(f"Provider request failed: {exc}") from exc
    if response.status_code >= 400:
        raise ProviderError(f"Provider error: {response.status_code} - {response.text}")

    data = response.json()
    address = data.get('input_address') or data.get('address')
    if not address:
        raise ProviderError("Provider did not return an address.")

    provider_reference = data.get('id') or data.get('payment_id') or ''
    return {
        'provider': 'blockcypher',
        'pay_address': address,
        'payment_id': provider_reference,
        'reference': provider_reference,
        'payload': data,
    }


def verify_transaction(symbol: str, tx_hash: str, expected_address: str | None = None) -> dict[str, Any]:
    provider = str(get_setting('CRYPTO_PROVIDER', default='manual')).lower()
    if provider != 'blockcypher':
        raise ProviderError("Provider not configured.")
    if symbol == 'USDT':
        raise ProviderError("USDT verification is not configured for this provider.")

    base_url = _blockcypher_base(symbol)
    url = f"{base_url}/txs/{tx_hash}"
    try:
        response = requests.get(url, timeout=20)
    except requests.RequestException as exc:
        raise ProviderError(f"Verification request failed: {exc}") from exc
    if response.status_code >= 400:
        raise ProviderError(f"Verification failed: {response.status_code} - {response.text}")

    data = response.json()
    addresses = set(data.get('addresses') or [])
    outputs = data.get('outputs') or []

    if expected_address:
        matches = any(expected_address in (output.get('addresses') or []) for output in outputs) or expected_address in addresses
    else:
        matches = True

    confirmations = int(data.get('confirmations') or 0)
    raw_total = data.get('total') or data.get('total_received') or 0

    if symbol == 'BTC':
        amount = Decimal(raw_total) / Decimal('100000000')
    else:
        amount = Decimal(raw_total) / Decimal('1000000000000000000')

    return {
        'matched': matches,
        'confirmations': confirmations,
        'amount': str(amount),
        'raw': data,
    }


def verify_and_update_deposit(deposit: Deposit) -> bool:
    if not deposit.transaction_hash:
        raise ProviderError("Missing transaction hash.")

    return refresh_confirmations(deposit)


def _schedule_next_check(deposit: Deposit) -> None:
    backoff_minutes = min(120, max(10, (deposit.check_attempts + 1) * 10))
    deposit.next_check_at = timezone.now() + timedelta(minutes=backoff_minutes)


def refresh_confirmations(deposit: Deposit) -> bool:
    if deposit.status in {'completed', 'rejected'}:
        return False
    if not deposit.transaction_hash:
        return False

    result = verify_transaction(deposit.crypto.symbol, deposit.transaction_hash, deposit.pay_address)
    deposit.verification_payload = result
    deposit.confirmations = int(result.get('confirmations') or 0)
    deposit.last_checked_at = timezone.now()
    deposit.check_attempts += 1

    matched = bool(result.get('matched'))
    if matched and deposit.confirmations >= deposit.target_confirmations:
        deposit.status = 'completed'
        deposit.completed_at = deposit.completed_at or timezone.now()
    elif deposit.check_attempts >= deposit.max_check_attempts:
        deposit.status = 'rejected'
    else:
        deposit.status = 'confirming'
        _schedule_next_check(deposit)

    deposit.save(
        update_fields=[
            'verification_payload',
            'confirmations',
            'last_checked_at',
            'check_attempts',
            'next_check_at',
            'status',
            'completed_at',
        ]
    )
    return deposit.status == 'completed'
