from decimal import Decimal
from typing import Literal

from django.db import transaction

from wallets.models import Wallet, Transaction, WalletTransfer

BalanceBucket = Literal['main', 'bonus', 'profit']


def _apply_amount(wallet: Wallet, bucket: BalanceBucket, amount: Decimal) -> None:
    if bucket == 'main':
        wallet.main_balance += amount
    elif bucket == 'bonus':
        wallet.bonus_balance += amount
    elif bucket == 'profit':
        wallet.profit_balance += amount
    else:
        raise ValueError("Invalid bucket")


def get_primary_wallet(user) -> Wallet | None:
    wallet = Wallet.objects.filter(user=user, wallet_type='primary').first()
    if wallet:
        return wallet
    try:
        return create_primary_wallet(user)
    except Exception:
        return None


def create_primary_wallet(user, *, name: str | None = None) -> Wallet:
    default_name = name or 'Primary Wallet'
    return Wallet.objects.create(
        user=user,
        name=default_name,
        wallet_type='primary',
        is_default=True,
        is_active=True,
    )


def create_wallet(
    user,
    *,
    name: str | None = None,
    wallet_type: str = 'trading',
    is_active: bool = True,
) -> Wallet:
    if wallet_type == 'primary':
        raise ValueError("Users cannot create primary wallets.")
    if wallet_type not in {'trading', 'savings'}:
        raise ValueError("Invalid wallet type.")
    default_name = 'Trading Wallet' if wallet_type == 'trading' else 'Savings Wallet'
    wallet = Wallet.objects.create(
        user=user,
        name=name or default_name,
        wallet_type=wallet_type,
        is_default=False,
        is_active=is_active,
    )
    return wallet


@transaction.atomic
def credit_wallet(wallet: Wallet, amount: Decimal, bucket: BalanceBucket, txn_type: str, meta: dict | None = None) -> None:
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    _apply_amount(wallet, bucket, amount)
    wallet.save(update_fields=['main_balance', 'bonus_balance', 'profit_balance'])
    Transaction.objects.create(
        user=wallet.user,
        wallet=wallet,
        txn_type=txn_type,
        amount=amount,
        balance_after=wallet.total_balance,
        meta=meta or {},
    )


@transaction.atomic
def debit_wallet(wallet: Wallet, amount: Decimal, bucket: BalanceBucket, txn_type: str, meta: dict | None = None) -> None:
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    _apply_amount(wallet, bucket, -amount)
    wallet.save(update_fields=['main_balance', 'bonus_balance', 'profit_balance'])
    Transaction.objects.create(
        user=wallet.user,
        wallet=wallet,
        txn_type=txn_type,
        amount=-amount,
        balance_after=wallet.total_balance,
        meta=meta or {},
    )


@transaction.atomic
def transfer_between_wallets(
    *,
    from_wallet: Wallet,
    to_wallet: Wallet,
    amount: Decimal,
    bucket: BalanceBucket = 'main',
    note: str = '',
) -> WalletTransfer:
    if from_wallet.id == to_wallet.id:
        raise ValueError("Choose two different wallets.")
    if from_wallet.user_id != to_wallet.user_id:
        raise ValueError("Wallets must belong to the same user.")
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    current_balance = getattr(from_wallet, f"{bucket}_balance")
    if amount > current_balance:
        raise ValueError("Insufficient balance in the source wallet.")

    debit_wallet(from_wallet, amount, bucket, 'transfer', {'to_wallet_id': str(to_wallet.id), 'note': note})
    credit_wallet(to_wallet, amount, bucket, 'transfer', {'from_wallet_id': str(from_wallet.id), 'note': note})
    return WalletTransfer.objects.create(
        user=from_wallet.user,
        from_wallet=from_wallet,
        to_wallet=to_wallet,
        amount=amount,
        bucket=bucket,
        note=note,
        status='completed',
    )
