from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from django.db import migrations


VALID_WALLET_TYPES = {'primary', 'trading', 'savings'}


def _is_valid_uuid(value: Any) -> bool:
    if value is None:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _pick_primary_candidate(wallets):
    def sort_key(item):
        is_default = 1 if item['is_default'] else 0
        created_at = item['created_at'] or ''
        name = item['name'] or ''
        name_boost = 1 if 'primary' in name.lower() else 0
        return (-name_boost, -is_default, created_at)

    return sorted(wallets, key=sort_key)[0]


def fix_wallet_ids_and_types(apps, schema_editor):
    connection = schema_editor.connection
    cursor = connection.cursor()
    constraints_disabled = False
    try:
        if connection.disable_constraint_checking():
            constraints_disabled = True
    except Exception:
        constraints_disabled = False

    try:
        cursor.execute(
            "SELECT id, user_id, wallet_type, is_default, created_at, name FROM wallets_wallet"
        )
        rows = cursor.fetchall()

        id_map: dict[str, str] = {}
        for row in rows:
            wallet_id = row[0]
            if not _is_valid_uuid(wallet_id):
                id_map[str(wallet_id)] = str(uuid.uuid4())

        def update_fk(table: str, column: str) -> None:
            for old_id, new_id in id_map.items():
                cursor.execute(
                    f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
                    [new_id, old_id],
                )

        if id_map:
            update_fk('wallets_transaction', 'wallet_id')
            update_fk('wallets_wallettransfer', 'from_wallet_id')
            update_fk('wallets_wallettransfer', 'to_wallet_id')
            update_fk('deposits_deposit', 'wallet_id')
            update_fk('withdrawals_withdrawal', 'wallet_id')
            update_fk('investments_userinvestment', 'wallet_id')

            for old_id, new_id in id_map.items():
                cursor.execute(
                    "UPDATE wallets_wallet SET id = %s WHERE id = %s",
                    [new_id, old_id],
                )

        cursor.execute(
            "SELECT id, user_id, wallet_type, is_default, created_at, name FROM wallets_wallet"
        )
        rows = cursor.fetchall()

        by_user: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_user[int(row[1])].append(
                {
                    'id': row[0],
                    'user_id': row[1],
                    'wallet_type': row[2],
                    'is_default': bool(row[3]),
                    'created_at': row[4],
                    'name': row[5],
                }
            )

        for wallets in by_user.values():
            primaries = [w for w in wallets if w['wallet_type'] == 'primary']
            if not primaries:
                primary = _pick_primary_candidate(wallets)
                primary['wallet_type'] = 'primary'
                primary['is_default'] = True
                primaries = [primary]

            if len(primaries) > 1:
                keep = _pick_primary_candidate(primaries)
                for w in primaries:
                    if w['id'] != keep['id']:
                        w['wallet_type'] = 'trading'
                        w['is_default'] = False

            for w in wallets:
                if w['wallet_type'] not in VALID_WALLET_TYPES:
                    w['wallet_type'] = 'trading'
                w['is_default'] = w['wallet_type'] == 'primary'

        for wallets in by_user.values():
            for w in wallets:
                cursor.execute(
                    "UPDATE wallets_wallet SET wallet_type = %s, is_default = %s WHERE id = %s",
                    [w['wallet_type'], 1 if w['is_default'] else 0, w['id']],
                )
    finally:
        if constraints_disabled:
            connection.enable_constraint_checking()


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0006_rename_is_primary_wallet_is_default_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_wallet_ids_and_types, migrations.RunPython.noop),
    ]
