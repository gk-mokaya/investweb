from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from supportchat.models import Conversation
from supportchat.services import append_message, mark_conversation_read, serialize_message


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation = None
        self.role = 'client'
        self.is_staff = bool(getattr(self.scope.get('user'), 'is_staff', False))
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        query = parse_qs(self.scope.get('query_string', b'').decode())
        self.token = (query.get('token') or [''])[0]
        self.conversation = await self._get_conversation()
        if not self.conversation:
            await self.close()
            return
        self.group_name = f"support_chat_{self.conversation.id}"
        self.role = 'admin' if self.is_staff else 'client'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._mark_read()
        await self.send_json({
            'type': 'conversation.ready',
            'conversation_id': str(self.conversation.id),
            'role': self.role,
        })

    async def disconnect(self, close_code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'message':
            text = (content.get('content') or '').strip()
            if not text:
                await self.send_json({'type': 'error', 'error': 'Message cannot be empty.'})
                return
            message = await self._create_message(text)
            payload = serialize_message(message)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat.message',
                    'payload': payload,
                    'conversation_id': str(self.conversation.id),
                },
            )
            return
        if action == 'mark_read':
            await self._mark_read()
            await self.send_json({
                'type': 'read.received',
                'conversation_id': str(self.conversation.id),
            })

    async def chat_message(self, event):
        await self.send_json({
            'type': 'message',
            'conversation_id': event['conversation_id'],
            'message': event['payload'],
        })

    @sync_to_async
    def _get_conversation(self):
        try:
            conversation = Conversation.objects.select_related('user').get(pk=self.conversation_id)
        except Conversation.DoesNotExist:
            return None
        user = self.scope.get('user')
        if self.is_staff:
            return conversation
        if user and not isinstance(user, AnonymousUser) and user.is_authenticated and conversation.user_id == user.id:
            return conversation
        if self.token and str(conversation.public_token) == self.token:
            return conversation
        return None

    @sync_to_async
    def _create_message(self, text):
        user = self.scope.get('user')
        sender_user = user if user and getattr(user, 'is_authenticated', False) else None
        sender_role = 'admin' if self.is_staff else 'client'
        message = append_message(self.conversation, sender_role=sender_role, content=text, sender_user=sender_user)
        return message

    @sync_to_async
    def _mark_read(self):
        mark_conversation_read(self.conversation, 'admin' if self.is_staff else 'client')
