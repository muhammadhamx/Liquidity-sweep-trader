from django.db import models
from django.utils import timezone
from .trade_execution import TradeExecution


class TradeManagement(models.Model):
    """Model to track trade management actions"""
    execution = models.ForeignKey(TradeExecution, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20)
    old_value = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    new_value = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    action_time = models.DateTimeField()
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'trade_management'
        ordering = ['-action_time']


