from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from kyc.models import KYCProfile, KYCVerificationEvent, KYCVerificationRun


@dataclass(frozen=True)
class VerificationStage:
    key: str
    label: str
    percent: int


VERIFICATION_STAGES = [
    VerificationStage('completeness', 'Checking completeness', 15),
    VerificationStage('integrity', 'Inspecting documents', 35),
    VerificationStage('identity', 'Matching identity details', 60),
    VerificationStage('risk', 'Running compliance checks', 85),
    VerificationStage('decision', 'Finalizing decision', 100),
]


def get_verification_channel_group(run_id: int) -> str:
    return f'kyc_verification_{run_id}'


def get_latest_verification_run(profile: KYCProfile) -> KYCVerificationRun | None:
    return profile.verification_runs.order_by('-created_at', '-id').first()


@transaction.atomic
def create_verification_run(profile: KYCProfile, *, actor=None) -> KYCVerificationRun:
    run = KYCVerificationRun.objects.create(
        profile=profile,
        status='queued',
        current_stage='queued',
        stage_label='Queued',
        progress_percent=0,
        metadata={
            'actor_id': getattr(actor, 'id', None),
            'missing_items': profile.missing_items(),
        },
    )
    _record_event(run, 'queued', 'Queued', 'queued', 'Verification queued for automatic processing.', 0)
    return run


def _record_event(run: KYCVerificationRun, stage_key: str, stage_label: str, status: str, message: str, percent: int) -> None:
    KYCVerificationEvent.objects.create(
        run=run,
        stage_key=stage_key,
        stage_label=stage_label,
        status=status,
        message=message,
        percent=percent,
    )
    stage_log = list(run.stage_log or [])
    stage_log.append({
        'stage_key': stage_key,
        'stage_label': stage_label,
        'status': status,
        'message': message,
        'percent': percent,
        'created_at': timezone.now().isoformat(),
    })
    run.stage_log = stage_log
    run.current_stage = stage_key
    run.stage_label = stage_label
    run.progress_percent = percent
    if status in {'verified', 'manual_review', 'rejected', 'failed'}:
        run.status = status
        run.completed_at = timezone.now()
    elif status == 'processing':
        run.status = 'processing'
        if not run.started_at:
            run.started_at = timezone.now()
    else:
        run.status = 'queued'
    run.save(update_fields=['status', 'current_stage', 'stage_label', 'progress_percent', 'stage_log', 'metadata', 'risk_score', 'error_message', 'started_at', 'completed_at', 'updated_at'])


def serialize_verification_run(run: KYCVerificationRun) -> dict[str, Any]:
    return {
        'id': run.id,
        'profile_id': run.profile_id,
        'status': run.status,
        'current_stage': run.current_stage,
        'stage_label': run.stage_label,
        'progress_percent': run.progress_percent,
        'risk_score': run.risk_score,
        'error_message': run.error_message,
        'stage_log': run.stage_log or [],
        'created_at': run.created_at.isoformat() if run.created_at else None,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'completed_at': run.completed_at.isoformat() if run.completed_at else None,
    }


def _estimate_risk_score(profile: KYCProfile) -> int:
    score = 0
    if profile.is_underage():
        score += 100
    if profile.source_of_funds == 'other' and not profile.source_of_funds_other:
        score += 20
    if not profile.tax_id:
        score += 20
    if len(profile.id_number or '') < 5:
        score += 15
    if not profile.phone_number:
        score += 10
    return min(score, 100)


def _file_present(upload) -> bool:
    return bool(upload and getattr(upload, 'name', ''))


def _validate_documents(profile: KYCProfile) -> list[str]:
    issues = []
    if not _file_present(profile.id_document_front):
        issues.append('Missing ID front document.')
    if not _file_present(profile.id_document_back):
        issues.append('Missing ID back document.')
    if not _file_present(profile.selfie_photo):
        issues.append('Missing selfie photo.')
    return issues


@transaction.atomic
def start_processing_if_ready(run_id: int) -> bool:
    run = KYCVerificationRun.objects.select_related('profile').select_for_update().get(pk=run_id)
    if run.status not in {'queued', 'processing'}:
        return False
    if run.started_at:
        return False
    run.status = 'processing'
    run.started_at = timezone.now()
    run.current_stage = 'completeness'
    run.stage_label = 'Checking completeness'
    run.progress_percent = 5
    run.save(update_fields=['status', 'started_at', 'current_stage', 'stage_label', 'progress_percent', 'updated_at'])
    _record_event(run, 'processing', 'Processing', 'processing', 'Automatic verification started.', 5)
    return True


async def run_automatic_verification(run_id: int) -> None:
    run = await asyncio.to_thread(_get_run_snapshot, run_id)
    if not run:
        return
    profile = run.profile
    risk_score = _estimate_risk_score(profile)
    results = {
        'missing_items': profile.missing_items(),
        'document_issues': _validate_documents(profile),
        'risk_score': risk_score,
    }

    await _push_stage(run_id, 'completeness', 'Checking completeness', 'processing', 'Validating required fields and uploads.', 15)
    await asyncio.sleep(0.8)
    if results['missing_items']:
        await _finish(run_id, 'manual_review', 'Automatic verification needs manual review because required details are missing.', 35, results, risk_score)
        return

    await _push_stage(run_id, 'integrity', 'Inspecting documents', 'processing', 'Checking uploaded document presence and consistency.', 35)
    await asyncio.sleep(0.8)
    if results['document_issues']:
        await _finish(run_id, 'manual_review', 'Documents need manual review.', 45, results, risk_score)
        return

    await _push_stage(run_id, 'identity', 'Matching identity details', 'processing', 'Comparing the identity fields captured in the form.', 60)
    await asyncio.sleep(0.8)
    if profile.is_underage():
        await _finish(run_id, 'rejected', 'Applicant is below the minimum age threshold.', 60, results, 100)
        return

    await _push_stage(run_id, 'risk', 'Running compliance checks', 'processing', 'Applying risk and compliance rules.', 85)
    await asyncio.sleep(0.8)
    if risk_score >= 60:
        await _finish(run_id, 'manual_review', 'Risk score is above the automatic approval threshold.', 85, results, risk_score)
        return

    await _push_stage(run_id, 'decision', 'Finalizing decision', 'processing', 'Applying final approval rules.', 95)
    await _apply_success(run_id, results, risk_score)


def _get_run_snapshot(run_id: int) -> KYCVerificationRun | None:
    return KYCVerificationRun.objects.select_related('profile', 'profile__user').filter(pk=run_id).first()


async def _push_stage(run_id: int, stage_key: str, stage_label: str, status: str, message: str, percent: int) -> None:
    await asyncio.to_thread(_push_stage_sync, run_id, stage_key, stage_label, status, message, percent)


def _push_stage_sync(run_id: int, stage_key: str, stage_label: str, status: str, message: str, percent: int) -> None:
    run = KYCVerificationRun.objects.select_related('profile').get(pk=run_id)
    with transaction.atomic():
        _record_event(run, stage_key, stage_label, status, message, percent)
        _broadcast_run_update(run, event_type='verification.progress')


async def _finish(run_id: int, final_status: str, message: str, percent: int, results: dict[str, Any], risk_score: int) -> None:
    await asyncio.to_thread(_finish_sync, run_id, final_status, message, percent, results, risk_score)


def _finish_sync(run_id: int, final_status: str, message: str, percent: int, results: dict[str, Any], risk_score: int) -> None:
    run = KYCVerificationRun.objects.select_related('profile').get(pk=run_id)
    profile = run.profile
    with transaction.atomic():
        run.risk_score = risk_score
        run.error_message = message
        run.metadata = {**(run.metadata or {}), **results}
        _record_event(run, run.current_stage or 'decision', run.stage_label or 'Decision', final_status, message, percent)
        run.save(update_fields=['risk_score', 'error_message', 'metadata', 'status', 'current_stage', 'stage_label', 'progress_percent', 'stage_log', 'started_at', 'completed_at', 'updated_at'])
        if final_status == 'manual_review':
            profile.status = 'pending'
            profile.review_note = message
            profile.verification_method = 'automated'
            profile.reviewed_at = None
            profile.save(update_fields=['status', 'review_note', 'verification_method', 'reviewed_at'])
        elif final_status == 'rejected':
            profile.status = 'rejected'
            profile.review_note = message
            profile.verification_method = 'automated'
            profile.reviewed_at = timezone.now()
            profile.save(update_fields=['status', 'review_note', 'verification_method', 'reviewed_at'])
        _broadcast_run_update(run, event_type='verification.completed')


async def _apply_success(run_id: int, results: dict[str, Any], risk_score: int) -> None:
    await asyncio.to_thread(_apply_success_sync, run_id, results, risk_score)


def _apply_success_sync(run_id: int, results: dict[str, Any], risk_score: int) -> None:
    run = KYCVerificationRun.objects.select_related('profile').get(pk=run_id)
    profile = run.profile
    with transaction.atomic():
        run.risk_score = risk_score
        run.error_message = ''
        run.metadata = {**(run.metadata or {}), **results}
        profile.mark_verified(method='automated', review_note='Automatically verified.')
        profile.save(update_fields=['status', 'reviewed_at', 'verification_method', 'review_note', 'revoked_at', 'revoked_by', 'revocation_note'])
        _record_event(run, 'decision', 'Automatic approval', 'verified', 'Automatic verification approved.', 100)
        run.save(update_fields=['risk_score', 'error_message', 'metadata', 'status', 'current_stage', 'stage_label', 'progress_percent', 'stage_log', 'started_at', 'completed_at', 'updated_at'])
        _broadcast_run_update(run, event_type='verification.completed')


def mark_run_failed(run_id: int, message: str) -> None:
    run = KYCVerificationRun.objects.select_related('profile').filter(pk=run_id).first()
    if not run:
        return
    with transaction.atomic():
        run.error_message = message
        _record_event(run, 'failed', 'Verification failed', 'failed', message, run.progress_percent)
        run.save(update_fields=['error_message', 'status', 'current_stage', 'stage_label', 'progress_percent', 'stage_log', 'started_at', 'completed_at', 'updated_at'])
        _broadcast_run_update(run, event_type='verification.completed')


def _broadcast_run_update(run: KYCVerificationRun, *, event_type: str) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = {
        'type': event_type,
        'run': serialize_verification_run(run),
        'profile_id': run.profile_id,
    }
    async_to_sync(channel_layer.group_send)(get_verification_channel_group(run.id), payload)
