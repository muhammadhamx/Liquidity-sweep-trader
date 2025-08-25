from rest_framework import serializers

class SymbolSerializer(serializers.Serializer):
    symbol = serializers.CharField(required=True)

class TimeframeSerializer(serializers.Serializer):
    symbol = serializers.CharField(required=True)
    timeframe = serializers.CharField(required=True)
    count = serializers.IntegerField(default=100, required=False)

class MT5ConnectionSerializer(serializers.Serializer):
    account = serializers.IntegerField(required=True)
    password = serializers.CharField(required=False, allow_blank=True)
    server = serializers.CharField(default="MetaQuotes-Demo", required=False)

class TradeExecutionSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=10, default='XAUUSD')
    trade_type = serializers.ChoiceField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    volume = serializers.FloatField(min_value=0.01)
    price = serializers.FloatField(required=False)
    stop_loss = serializers.FloatField(required=False)
    take_profit = serializers.FloatField(required=False)
    deviation = serializers.IntegerField(default=20, min_value=1, max_value=100)
    comment = serializers.CharField(max_length=255, required=False, default='API Trade')