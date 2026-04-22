from __future__ import annotations

from typing import Any

from adminpanel.models import AuditLog


def log_action(actor, action: str, target_type: str = '', target_id: str = '', meta: dict[str, Any] | None = None) -> None:
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else '',
        meta=meta or {},
    )
