from rest_framework import serializers

from .models import Click


class ClickCreateSerializer(serializers.ModelSerializer):
    """Validates one click reported by the shortener.

    `city` and `country` are accepted but never populated by the shortener —
    geo-IP lookup is not part of this module. They exist so the schema does not
    change when it is added.
    """

    class Meta:
        model = Click
        fields = ['id', 'url_id', 'clicked_at', 'ip_address', 'city', 'country',
                  'user_agent', 'referrer']
        read_only_fields = ['id', 'clicked_at']
