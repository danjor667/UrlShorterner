from rest_framework import serializers

from .models import Click, URLProjection


class ClickCreateSerializer(serializers.ModelSerializer):
    """Validates one click reported by the shortener.
    """

    class Meta:
        model = Click
        fields = ['id', 'url_id', 'clicked_at', 'ip_address', 'city', 'country',
                  'user_agent', 'referrer']
        read_only_fields = ['id', 'clicked_at']


class URLProjectionSerializer(serializers.ModelSerializer):
    """The shortener's view of a URL, as this service is allowed to see it."""


    url_id = serializers.IntegerField()

    class Meta:
        model = URLProjection
        fields = ['url_id', 'short_code', 'custom_alias', 'original_url', 'owner_id', 'is_active']


class ClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = Click
        fields = ['id', 'clicked_at', 'ip_address', 'city', 'country', 'user_agent', 'referrer']


class AnalyticsSerializer(serializers.Serializer):
    """Premium-only click breakdown for a single URL."""

    short_code = serializers.CharField()
    original_url = serializers.URLField()
    total_clicks = serializers.IntegerField()
    unique_visitors = serializers.IntegerField()
    clicks_by_country = serializers.DictField(child=serializers.IntegerField())
    recent_clicks = ClickSerializer(many=True)
