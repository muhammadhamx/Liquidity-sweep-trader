from django.db import models
from django.utils import timezone


class TradingSession(models.Model):
    """Model to track trading sessions and state machine"""
    SESSION_CHOICES = [
        ('ASIAN', 'Asian Session'),
        ('LONDON', 'London Session'),
        ('NEW_YORK', 'New York Session'),
    ]

    STATE_CHOICES = [
        ('IDLE', 'Idle'),
        ('SWEPT', 'Sweep Detected'),
        ('CONFIRMED', 'Reversal Confirmed'),
        ('ARMED', 'Armed for Entry'),
        ('IN_TRADE', 'In Trade'),
        ('COOLDOWN', 'Cooldown'),
    ]

    BIAS_CHOICES = [
        ('BULLISH', 'Bullish'),
        ('BEARISH', 'Bearish'),
        ('NEUTRAL', 'Neutral'),
    ]

    session_date = models.DateField()
    session_type = models.CharField(max_length=20, choices=SESSION_CHOICES)
    current_state = models.CharField(max_length=20, choices=STATE_CHOICES, default='IDLE')
    asian_range_high = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    asian_range_low = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    asian_range_midpoint = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    asian_range_size = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    asian_range_grade = models.CharField(max_length=20, null=True, blank=True)
    sweep_threshold = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sweep_direction = models.CharField(max_length=10, null=True, blank=True)
    sweep_time = models.DateTimeField(null=True, blank=True)
    confirmation_time = models.DateTimeField(null=True, blank=True)
    armed_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Additional fields found in database
    atr_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    bos_choch_confirmed = models.BooleanField(default=False)
    cooldown_reason = models.CharField(max_length=100, null=True, blank=True)
    cooldown_until = models.DateTimeField(null=True, blank=True)
    current_daily_loss = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_daily_trades = models.IntegerField(default=0)
    daily_bias = models.CharField(max_length=10, choices=BIAS_CHOICES, null=True, blank=True)
    daily_loss_limit = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    daily_trade_count_limit = models.IntegerField(default=3)
    displacement_atr_ratio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    entry_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    entry_time = models.DateTimeField(null=True, blank=True)
    h4_bias = models.CharField(max_length=10, choices=BIAS_CHOICES, null=True, blank=True)
    spread_pips = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sweep_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)

    class Meta:
        db_table = 'trading_session'
        ordering = ['-session_date', '-created_at']


