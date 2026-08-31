from django.db.models import Q
from rest_framework import serializers

from .models import URL


class URLCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = URL
        fields = ['id', 'original_url', 'custom_alias', 'expires_at']

    def validate_custom_alias(self, value):
        """Reject an alias that any existing URL already answers to.

        Checked against `short_code` as well as `custom_alias`: a code is
        reachable by either column, so an alias colliding with someone's
        generated code would make the redirect ambiguous.
        """
        if not value:
            return value
        if URL.objects.filter(Q(short_code=value) | Q(custom_alias=value)).exists():
            raise serializers.ValidationError('This alias is already taken.')
        return value


class URLDetailSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = URL
        fields = ['id', 'original_url', 'short_code', 'custom_alias', 'short_url',
                  'is_active', 'expires_at', 'click_count', 'created_at']

    def get_short_url(self, obj) -> str:
        request = self.context.get('request')
        code = obj.active_code
        if request:
            return request.build_absolute_uri(f'/{code}/')
        return f'/{code}/'
