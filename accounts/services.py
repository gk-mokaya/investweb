from accounts.models import Notification


def create_notification(user, title: str, message: str = '', level: str = 'info') -> None:
    if not user:
        return
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        level=level,
    )
