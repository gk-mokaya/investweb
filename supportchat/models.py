import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_conversations')
    guest_name = models.CharField(max_length=120, blank=True, default='')
    guest_email = models.EmailField(blank=True, default='')
    subject = models.CharField(max_length=160, blank=True, default='Support chat')
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    unread_admin_count = models.PositiveIntegerField(default=0)
    unread_client_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-last_message_at', '-created_at')

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        if self.user_id and self.user:
            return self.user.get_full_name() or self.user.username
        if self.guest_name:
            return self.guest_name
        return 'Guest visitor'

    @property
    def contact_label(self) -> str:
        if self.user_id and self.user:
            return self.user.email or self.user.username
        return self.guest_email or 'Anonymous visitor'


class Message(models.Model):
    ROLE_CHOICES = [
        ('client', 'Client'),
        ('admin', 'Admin'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    sender_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_messages')
    content = models.TextField()
    attachment = models.FileField(upload_to='supportchat/messages/', blank=True, null=True)
    is_read_by_client = models.BooleanField(default=False)
    is_read_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self) -> str:
        return f"{self.conversation_id} - {self.sender_role}"
