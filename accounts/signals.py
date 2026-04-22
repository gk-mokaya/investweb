from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import UserProfile
from settingsconfig.utils import get_setting, get_setting_decimal
from adminpanel.utils import log_action
from accounts.models import LoginLog
from accounts.services import create_notification
from kyc.models import KYCProfile


@receiver(post_save, sender=User)
def create_profile_wallet_bonus(sender, instance: User, created: bool, **kwargs) -> None:
    if not created:
        return

    UserProfile.objects.create(user=instance)

    from wallets.services import credit_wallet, create_primary_wallet
    from investments.models import BonusTracker

    wallet = create_primary_wallet(instance, name='Primary Wallet')

    bonus_amount = get_setting_decimal('WELCOME_BONUS', default='50')
    multiplier = get_setting_decimal('BONUS_PROFIT_MULTIPLIER', default='3')

    required_profit = bonus_amount * multiplier
    BonusTracker.objects.create(
        user=instance,
        bonus_amount=bonus_amount,
        required_profit=required_profit,
    )

    if bonus_amount > 0:
        credit_wallet(wallet, bonus_amount, 'main', 'bonus', {'reason': 'welcome_bonus'})

    KYCProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
    last_log = LoginLog.objects.filter(user=user).order_by('-created_at').first()
    LoginLog.objects.create(user=user, ip_address=ip, user_agent=user_agent)
    log_action(user, 'login', 'user', user.id, {'ip': ip})
    if not last_log:
        bonus_amount = get_setting_decimal('WELCOME_BONUS', default='50')
        if bonus_amount > 0:
            currency = str(get_setting('CURRENCY', default='USD') or 'USD')
            create_notification(
                user,
                "Welcome bonus credited",
                f"You have received {bonus_amount} {currency} welcome bonus in your primary wallet.",
                level='success',
            )
    if last_log and last_log.ip_address and last_log.ip_address != ip:
        create_notification(
            user,
            "New login detected",
            f"Your account was accessed from a new IP: {ip}. If this wasn't you, reset your password.",
            level='warning',
        )
