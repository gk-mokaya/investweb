from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from supportchat.models import Conversation, Message


def _mark_read_flags(sender_role: str) -> dict:
    if sender_role == 'admin':
        return {'is_read_by_admin': True, 'is_read_by_client': False}
    return {'is_read_by_admin': False, 'is_read_by_client': True}


@transaction.atomic
def get_or_create_conversation_for_user(user, *, guest_name='', guest_email=''):
    conversation = Conversation.objects.select_for_update().filter(user=user, status='open').first()
    if conversation:
        updated = False
        if guest_name and not conversation.guest_name:
            conversation.guest_name = guest_name
            updated = True
        if guest_email and not conversation.guest_email:
            conversation.guest_email = guest_email
            updated = True
        if updated:
            conversation.save(update_fields=['guest_name', 'guest_email', 'updated_at'])
        return conversation, False
    conversation = Conversation.objects.create(
        user=user,
        guest_name=guest_name or user.get_full_name() or user.username,
        guest_email=guest_email or user.email or '',
    )
    return conversation, True


@transaction.atomic
def get_or_create_guest_conversation(*, guest_name='', guest_email='', token=None):
    conversation = None
    if token:
        conversation = Conversation.objects.select_for_update().filter(public_token=token).first()
    if conversation:
        updated = False
        if guest_name and not conversation.guest_name:
            conversation.guest_name = guest_name
            updated = True
        if guest_email and not conversation.guest_email:
            conversation.guest_email = guest_email
            updated = True
        if updated:
            conversation.save(update_fields=['guest_name', 'guest_email', 'updated_at'])
        return conversation, False
    conversation = Conversation.objects.create(
        guest_name=guest_name or 'Guest visitor',
        guest_email=guest_email or '',
    )
    return conversation, True


@transaction.atomic
def append_message(conversation, *, sender_role, content='', attachment=None, sender_user=None):
    message = Message.objects.create(
        conversation=conversation,
        sender_role=sender_role,
        sender_user=sender_user,
        content=(content or '').strip(),
        attachment=attachment,
        **_mark_read_flags(sender_role),
    )
    conversation.last_message_at = timezone.now()
    if sender_role == 'admin':
        conversation.unread_client_count += 1
        conversation.unread_admin_count = 0
    else:
        conversation.unread_admin_count += 1
        conversation.unread_client_count = 0
    conversation.save(update_fields=['last_message_at', 'unread_admin_count', 'unread_client_count', 'updated_at'])
    return message


@transaction.atomic
def mark_conversation_read(conversation, role):
    update_fields = []
    if role == 'admin' and conversation.unread_admin_count:
        conversation.unread_admin_count = 0
        update_fields.append('unread_admin_count')
    if role == 'client' and conversation.unread_client_count:
        conversation.unread_client_count = 0
        update_fields.append('unread_client_count')
    if update_fields:
        conversation.save(update_fields=update_fields + ['updated_at'])


def serialize_message(message):
    sender_name = ''
    if message.sender_role == 'admin' and message.sender_user:
        sender_name = message.sender_user.get_full_name() or message.sender_user.username
    elif message.conversation.user_id and message.sender_role == 'client':
        sender_name = message.conversation.display_name
    else:
        sender_name = message.conversation.display_name
    attachment_url = ''
    attachment_name = ''
    if getattr(message, 'attachment', None):
        attachment = message.attachment
        if attachment:
            attachment_url = attachment.url
            attachment_name = attachment.name.rsplit('/', 1)[-1]
    return {
        'id': str(message.id),
        'conversation_id': str(message.conversation_id),
        'sender_role': message.sender_role,
        'sender_name': sender_name,
        'content': message.content,
        'attachment_url': attachment_url,
        'attachment_name': attachment_name,
        'created_at': message.created_at.isoformat(),
        'time_label': timezone.localtime(message.created_at).strftime('%b %d, %H:%M'),
    }


def broadcast_message(message):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"support_chat_{message.conversation_id}",
        {
            'type': 'chat.message',
            'payload': serialize_message(message),
            'conversation_id': str(message.conversation_id),
        },
    )
