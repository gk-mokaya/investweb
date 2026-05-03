from django.contrib import admin

from supportchat.models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'contact_label', 'status', 'unread_admin_count', 'unread_client_count', 'last_message_at')
    list_filter = ('status',)
    search_fields = ('guest_name', 'guest_email', 'user__username', 'user__email')
    readonly_fields = ('public_token', 'created_at', 'updated_at', 'last_message_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender_role', 'created_at')
    list_filter = ('sender_role',)
    search_fields = ('content',)
