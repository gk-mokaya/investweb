from payments.models import PaymentConfiguration, CryptoCurrency


def get_payment_configuration() -> PaymentConfiguration:
    config = PaymentConfiguration.objects.first()
    if config:
        return config
    return PaymentConfiguration.objects.create()


def get_active_cryptos():
    return CryptoCurrency.objects.filter(is_active=True).order_by('symbol', 'network')
