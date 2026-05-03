from django.urls import path

from supportchat.views import ChatMarkReadView, ChatMessagesView, ChatStartView, StaffChatInboxView


urlpatterns = [
    path('chat/start/', ChatStartView.as_view(), name='support_chat_start'),
    path('chat/conversations/<uuid:conversation_id>/messages/', ChatMessagesView.as_view(), name='support_chat_messages'),
    path('chat/conversations/<uuid:conversation_id>/mark-read/', ChatMarkReadView.as_view(), name='support_chat_mark_read'),
    path('staff/chat/', StaffChatInboxView.as_view(), name='staff_chat_inbox'),
]
