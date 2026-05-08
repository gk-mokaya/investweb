from wallets.models import Wallet
from wallets.services import get_primary_wallet


def wallet_summary(request):
    if request.user.is_authenticated:
        from investments.services import get_investment_account

        wallets = Wallet.objects.filter(user=request.user).order_by('-is_default', 'created_at')
        wallet = next((item for item in wallets if item.wallet_type == 'primary'), None)
        if wallet is None:
            wallet = get_primary_wallet(request.user)
        investment_account = get_investment_account(request.user)
        return {
            'WALLET_SUMMARY': wallet,
            'PRIMARY_WALLET': wallet,
            'INVESTMENT_SUMMARY': investment_account,
            'WALLETS': wallets,
        }
    return {'WALLET_SUMMARY': None, 'PRIMARY_WALLET': None, 'INVESTMENT_SUMMARY': None, 'WALLETS': []}
