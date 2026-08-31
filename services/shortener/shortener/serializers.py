from django.db.models import Q
from rest_framework import serializers

from .models import URL, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


class URLCreateSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
        help_text='Tag names; unknown names are created.',
    )

    class Meta:
        model = URL
        fields = ['id', 'original_url', 'custom_alias', 'expires_at', 'tags']

    def validate_custom_alias(self, value):
        if value and URL.objects.filter(Q(short_code=value) | Q(custom_alias=value)).exists():
            raise serializers.ValidationError('This alias is already taken.')
        return value

    def create(self, validated_data):
        tag_names = validated_data.pop('tags', [])
        url = super().create(validated_data)
        if tag_names:
            url.tags.set([Tag.objects.get_or_create(name=name)[0] for name in tag_names])
        return url


class URLDetailSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = URL
        # `owner_id` is exposed as the bare integer it is. There is no nested
        # owner object: rendering one would mean calling the auth service on
        # every row of the list endpoint.
        fields = ['id', 'original_url', 'short_code', 'custom_alias', 'short_url', 'owner_id',
                  'tags', 'title', 'description', 'favicon', 'is_active', 'expires_at',
                  'click_count', 'created_at']
        read_only_fields = ['owner_id']

    def get_short_url(self, obj) -> str:
        request = self.context.get('request')
        code = obj.active_code
        if request:
            return request.build_absolute_uri(f'/{code}/')
        return f'/{code}/'
