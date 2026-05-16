from __future__ import annotations

import asyncio
import threading
from typing import Final

from kyc.services import mark_run_failed, run_automatic_verification, start_processing_if_ready
from django.db import close_old_connections

_ACTIVE_RUNS: set[int] = set()
_LOCK: Final = threading.Lock()


def start_verification_background(run_id: int) -> bool:
    with _LOCK:
        if run_id in _ACTIVE_RUNS:
            return False
        _ACTIVE_RUNS.add(run_id)

    def _runner() -> None:
        try:
            close_old_connections()
            if not start_processing_if_ready(run_id):
                return
            asyncio.run(run_automatic_verification(run_id))
        except Exception as exc:  # pragma: no cover - defensive background guard
            mark_run_failed(run_id, f'Automatic verification failed: {exc}')
        finally:
            close_old_connections()
            with _LOCK:
                _ACTIVE_RUNS.discard(run_id)

    thread = threading.Thread(target=_runner, name=f'kyc-verification-{run_id}', daemon=True)
    thread.start()
    return True
