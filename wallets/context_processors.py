from wallets.models import Wallet
from wallets.services import get_primary_wallet


def wallet_summary(request):
    if request.user.is_authenticated:
        wallet = get_primary_wallet(request.user)
        wallets = Wallet.objects.filter(user=request.user).order_by('-is_default', 'created_at')
        return {'WALLET_SUMMARY': wallet, 'WALLETS': wallets}
    return {'WALLET_SUMMARY': None, 'WALLETS': []}
