from django.db import models
from django.utils import timezone
from .trading_session import TradingSession


class ConfluenceCheck(models.Model):
    """Model to track confluence checks"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=10)
    bias = models.CharField(max_length=20)
    trend_strength = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    atr_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    adx_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    spread = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    velocity_spike = models.BooleanField(default=False)
    news_risk = models.BooleanField(default=False)
    news_buffer_minutes = models.IntegerField(default=0)
    passed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'confluence_check'
        ordering = ['-created_at']


