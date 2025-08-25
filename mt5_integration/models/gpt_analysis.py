from django.db import models
from django.utils import timezone
from .trading_session import TradingSession
from .trade_signal import TradeSignal


class GPTAnalysis(models.Model):
    """Model to store GPT analysis and decisions"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE, null=True, blank=True)
    signal = models.ForeignKey(TradeSignal, on_delete=models.CASCADE, null=True, blank=True)
    analysis_type = models.CharField(max_length=20)
    prompt = models.TextField()
    response = models.TextField()
    tokens_used = models.IntegerField()
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    decision = models.CharField(max_length=20, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'gpt_analysis'
        ordering = ['-created_at']


