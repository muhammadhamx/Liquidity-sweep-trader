from django.db import models
from django.utils import timezone
from .trade_signal import TradeSignal


class TradeExecution(models.Model):
    """Model to track trade executions"""
    signal = models.ForeignKey(TradeSignal, on_delete=models.CASCADE)
    order_id = models.IntegerField()
    execution_price = models.DecimalField(max_digits=10, decimal_places=5)
    execution_time = models.DateTimeField()
    status = models.CharField(max_length=20, default='EXECUTED')
    stop_loss_hit = models.BooleanField(default=False)
    take_profit_1_hit = models.BooleanField(default=False)
    take_profit_2_hit = models.BooleanField(default=False)
    breakeven_moved = models.BooleanField(default=False)
    trailing_stop_active = models.BooleanField(default=False)
    pnl = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'trade_execution'
        ordering = ['-execution_time']


