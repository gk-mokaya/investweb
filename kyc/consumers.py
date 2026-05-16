from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from kyc.models import KYCVerificationRun
from kyc.services import (
    get_verification_channel_group,
    serialize_verification_run,
)


class KYCVerificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.run_id = self.scope['url_route']['kwargs']['run_id']
        self.run = await self._get_run()
        if not self.run:
            await self.close()
            return

        self.group_name = get_verification_channel_group(self.run.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'verification.ready',
            'run': serialize_verification_run(self.run),
        })

    async def disconnect(self, close_code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'refresh':
            self.run = await self._get_run()
            if self.run:
                await self.send_json({
                    'type': 'verification.state',
                    'run': serialize_verification_run(self.run),
                })

    async def verification_progress(self, event):
        await self.send_json({
            'type': 'verification.progress',
            'run': event['run'],
        })

    async def verification_completed(self, event):
        await self.send_json({
            'type': 'verification.completed',
            'run': event['run'],
        })

    @database_sync_to_async
    def _get_run(self):
        try:
            run = KYCVerificationRun.objects.select_related('profile', 'profile__user').get(pk=self.run_id)
        except KYCVerificationRun.DoesNotExist:
            return None
        user = self.scope.get('user')
        if user and not isinstance(user, AnonymousUser) and user.is_authenticated:
            if run.profile.user_id != user.id and not user.is_staff:
                return None
            return run
        return None
