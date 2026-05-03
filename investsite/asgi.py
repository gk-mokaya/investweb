"""
ASGI config for investsite project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investsite.settings')

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import investsite.routing

django_asgi_application = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_application,
    'websocket': AuthMiddlewareStack(
        URLRouter(investsite.routing.websocket_urlpatterns)
    ),
})
