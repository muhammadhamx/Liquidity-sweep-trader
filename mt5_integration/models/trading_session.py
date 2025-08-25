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

    class Meta:
        db_table = 'trading_session'
        ordering = ['-session_date', '-created_at']


