from django.urls import path

from supportchat.consumers import ChatConsumer


websocket_urlpatterns = [
    path('ws/support-chat/<uuid:conversation_id>/', ChatConsumer.as_asgi(), name='support_chat_ws'),
]
