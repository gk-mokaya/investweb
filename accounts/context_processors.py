from accounts.models import Notification


def notifications(request):
    if request.user.is_authenticated:
        unread_qs = Notification.objects.filter(user=request.user, is_read=False).only(
            'id',
            'user_id',
            'title',
            'message',
            'level',
            'is_read',
            'created_at',
        ).order_by('-created_at')
        items = unread_qs[:8]
        unread = unread_qs.count()
        return {'NOTIFICATIONS': items, 'NOTIF_UNREAD': unread}
    return {'NOTIFICATIONS': [], 'NOTIF_UNREAD': 0}
