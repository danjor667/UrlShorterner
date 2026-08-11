from rest_framework import serializers
from .models import URL


class URLCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = URL
        fields = ['id', 'original_url', 'custom_alias', 'expires_at']

    def create(self, validated_data):
        alias = validated_data.get('custom_alias')
        if alias and URL.objects.filter(short_code=alias).exists():
            raise serializers.ValidationError({'custom_alias': 'This alias is already taken.'})
        return super().create(validated_data)


class URLDetailSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = URL
        fields = ['id', 'original_url', 'short_code', 'custom_alias', 'short_url',
                  'is_active', 'expires_at', 'click_count', 'created_at']

    def get_short_url(self, obj):
        request = self.context.get('request')
        code = obj.active_code
        if request:
            return request.build_absolute_uri(f'/{code}/')
        return f'/{code}/'
