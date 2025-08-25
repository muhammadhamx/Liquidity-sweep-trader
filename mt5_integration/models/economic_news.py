from django.db import models
from django.utils import timezone


class EconomicNews(models.Model):
    """Model to store economic news events"""
    SEVERITY_CHOICES = [
        ('LOW', 'Low Impact'),
        ('MEDIUM', 'Medium Impact'),
        ('HIGH', 'High Impact'),
        ('CRITICAL', 'Critical Impact'),
    ]

    event_name = models.CharField(max_length=200)
    currency = models.CharField(max_length=10)
    release_time = models.DateTimeField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    buffer_minutes = models.IntegerField(default=30)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'economic_news'
        ordering = ['-release_time']


