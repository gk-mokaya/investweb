from kyc.models import KYCProfile


def kyc_status(request):
    if request.user.is_authenticated:
        profile = KYCProfile.objects.filter(user=request.user).first()
        return {'KYC_PROFILE': profile}
    return {'KYC_PROFILE': None}
