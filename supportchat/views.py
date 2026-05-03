import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from supportchat.models import Conversation
from supportchat.services import (
    append_message,
    broadcast_message,
    get_or_create_conversation_for_user,
    get_or_create_guest_conversation,
    mark_conversation_read,
    serialize_message,
)


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class ChatStartView(View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        guest_name = (request.POST.get('guest_name') or '').strip()
        guest_email = (request.POST.get('guest_email') or '').strip()
        guest_token = request.POST.get('token') or request.session.get('support_chat_token')

        if request.user.is_authenticated:
            conversation, created = get_or_create_conversation_for_user(
                request.user,
                guest_name=guest_name,
                guest_email=guest_email,
            )
        else:
            conversation, created = get_or_create_guest_conversation(
                guest_name=guest_name,
                guest_email=guest_email,
                token=guest_token,
            )
            request.session['support_chat_token'] = str(conversation.public_token)
            request.session.modified = True

        messages = [serialize_message(message) for message in conversation.messages.select_related('sender_user')[:40]]
        return JsonResponse({
            'ok': True,
            'created': created,
            'conversation': {
                'id': str(conversation.id),
                'token': str(conversation.public_token),
                'status': conversation.status,
                'display_name': conversation.display_name,
                'subject': conversation.subject,
                'contact_label': conversation.contact_label,
                'unread_admin_count': conversation.unread_admin_count,
                'unread_client_count': conversation.unread_client_count,
            },
            'messages': messages,
        })


class ChatMessagesView(View):
    http_method_names = ['get', 'post']

    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not self._can_access(request, conversation):
            return JsonResponse({'ok': False, 'error': 'Not allowed'}, status=403)
        if request.user.is_staff:
            mark_conversation_read(conversation, 'admin')
        elif request.user.is_authenticated or request.GET.get('token') == str(conversation.public_token):
            mark_conversation_read(conversation, 'client')
        messages = [serialize_message(message) for message in conversation.messages.select_related('sender_user')]
        return JsonResponse({
            'ok': True,
            'conversation': {
                'id': str(conversation.id),
                'token': str(conversation.public_token),
                'display_name': conversation.display_name,
                'subject': conversation.subject,
                'status': conversation.status,
                'unread_admin_count': conversation.unread_admin_count,
                'unread_client_count': conversation.unread_client_count,
            },
            'messages': messages,
        })

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not self._can_access(request, conversation):
            return JsonResponse({'ok': False, 'error': 'Not allowed'}, status=403)
        content = (request.POST.get('content') or '').strip()
        attachment = request.FILES.get('attachment')
        if attachment and not (getattr(attachment, 'content_type', '') or '').startswith('image/'):
            return JsonResponse({'ok': False, 'error': 'Please upload an image file.'}, status=400)
        if not content and not attachment:
            return JsonResponse({'ok': False, 'error': 'Message cannot be empty.'}, status=400)
        sender_role = 'admin' if request.user.is_staff else 'client'
        sender_user = request.user if request.user.is_authenticated else None
        message = append_message(conversation, sender_role=sender_role, content=content, attachment=attachment, sender_user=sender_user)
        broadcast_message(message)
        if request.user.is_staff:
            mark_conversation_read(conversation, 'admin')
        elif request.user.is_authenticated or request.POST.get('token') == str(conversation.public_token) or request.session.get('support_chat_token') == str(conversation.public_token):
            mark_conversation_read(conversation, 'client')
        return JsonResponse({
            'ok': True,
            'conversation': {
                'id': str(conversation.id),
                'token': str(conversation.public_token),
                'display_name': conversation.display_name,
                'subject': conversation.subject,
                'status': conversation.status,
                'unread_admin_count': conversation.unread_admin_count,
                'unread_client_count': conversation.unread_client_count,
            },
            'message': serialize_message(message),
        })

    def _can_access(self, request, conversation):
        if request.user.is_staff:
            return True
        if request.user.is_authenticated and conversation.user_id == request.user.id:
            return True
        token = request.GET.get('token') or request.session.get('support_chat_token')
        return token and token == str(conversation.public_token)


class ChatMarkReadView(View):
    http_method_names = ['post']

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not self._can_access(request, conversation):
            return JsonResponse({'ok': False, 'error': 'Not allowed'}, status=403)
        role = 'admin' if request.user.is_staff else 'client'
        mark_conversation_read(conversation, role)
        return JsonResponse({
            'ok': True,
            'unread_admin_count': conversation.unread_admin_count,
            'unread_client_count': conversation.unread_client_count,
        })

    def _can_access(self, request, conversation):
        if request.user.is_staff:
            return True
        if request.user.is_authenticated and conversation.user_id == request.user.id:
            return True
        token = request.POST.get('token') or request.session.get('support_chat_token')
        return token and token == str(conversation.public_token)


class StaffChatInboxView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'supportchat/staff_inbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation_qs = Conversation.objects.select_related('user').prefetch_related('messages').order_by('-last_message_at', '-created_at')
        conversation_id = self.request.GET.get('conversation')
        selected = None
        if conversation_id:
            selected = conversation_qs.filter(pk=conversation_id).first()
        if not selected:
            selected = conversation_qs.first()
        if selected:
            mark_conversation_read(selected, 'admin')
        context['conversations'] = conversation_qs[:40]
        context['inbox_stats'] = {
            'total': conversation_qs.count(),
            'open': conversation_qs.filter(status='open').count(),
            'unread': conversation_qs.filter(unread_admin_count__gt=0).count(),
        }
        context['selected_conversation'] = selected
        context['selected_messages'] = selected.messages.select_related('sender_user').all() if selected else []
        context['selected_messages_json'] = json.dumps([serialize_message(message) for message in context['selected_messages']])
        context['selected_conversation_json'] = json.dumps({
            'id': str(selected.id) if selected else '',
            'token': str(selected.public_token) if selected else '',
        })
        return context
