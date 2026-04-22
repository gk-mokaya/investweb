from django.db import models


class PaymentConfiguration(models.Model):
    MODE_CHOICES = [
        ('manual', 'Manual Only'),
        ('automated', 'Automated Only'),
        ('hybrid', 'Hybrid'),
    ]

    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='manual')
    enable_deposits = models.BooleanField(default=True)
    enable_withdrawals = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"PaymentConfiguration ({self.mode})"


class CryptoCurrency(models.Model):
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10)
    network = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('symbol', 'network')

    def __str__(self) -> str:
        return f"{self.symbol} ({self.network})"
