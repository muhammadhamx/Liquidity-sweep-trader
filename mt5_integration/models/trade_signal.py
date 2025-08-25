from django.db import models
from django.utils import timezone
from .trading_session import TradingSession
from .liquidity_sweep import LiquiditySweep


class TradeSignal(models.Model):
    """Enhanced model to store trade signals with state machine integration"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE, null=True, blank=True)
    sweep = models.ForeignKey(LiquiditySweep, on_delete=models.CASCADE, null=True, blank=True)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    signal_type = models.CharField(max_length=10, choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    entry_price = models.DecimalField(max_digits=10, decimal_places=5)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=5)
    take_profit_1 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    take_profit_2 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    volume = models.DecimalField(max_digits=10, decimal_places=2)
    risk_percentage = models.DecimalField(max_digits=4, decimal_places=2, default=0.5)
    risk_reward_ratio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=20, choices=TradingSession.STATE_CHOICES, default='IDLE')
    gpt_opinion = models.TextField(null=True, blank=True)
    gpt_tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trade_signal'
        ordering = ['-created_at']


