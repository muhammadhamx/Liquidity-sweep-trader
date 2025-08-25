from django.db import models
from django.utils import timezone
from .trading_session import TradingSession


class LiquiditySweep(models.Model):
    """Model to track liquidity sweeps"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    sweep_direction = models.CharField(max_length=10)
    sweep_price = models.DecimalField(max_digits=10, decimal_places=5)
    sweep_threshold = models.DecimalField(max_digits=8, decimal_places=2)
    sweep_time = models.DateTimeField()
    confirmation_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    confirmation_time = models.DateTimeField(null=True, blank=True)
    displacement_atr = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    displacement_multiplier = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='DETECTED')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'liquidity_sweep'
        ordering = ['-sweep_time']


