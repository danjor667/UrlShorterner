from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from common.permissions import caller_id, has_premium

from .models import URL, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


class TagNamesMixin:
    """Shared write-only `tags` field handling for create and update."""

    @staticmethod
    def _apply_tags(url, tag_names):
        url.tags.set([Tag.objects.get_or_create(name=name)[0] for name in tag_names])


class URLCreateSerializer(TagNamesMixin, serializers.ModelSerializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
        help_text='Tag names; unknown names are created.',
    )

    class Meta:
        model = URL
        fields = ['id', 'original_url', 'custom_alias', 'expires_at', 'tags']

    @property
    def _user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def validate_custom_alias(self, value):
        if not value:
            return value
        user = self._user
        # Module 7: custom aliases are a Premium feature. Read through the
        # shared helper: `request.user` here is a TokenUser with claims, not a
        # row with a `has_premium_access` property.
        if user is not None and not has_premium(user):
            raise serializers.ValidationError('Custom aliases require a Premium account.')
        if URL.objects.filter(Q(short_code=value) | Q(custom_alias=value)).exists():
            raise serializers.ValidationError('This alias is already taken.')
        return value

    def validate(self, attrs):
        user = self._user
        # Module 7: free accounts cap out at FREE_TIER_URL_LIMIT URLs.
        if user is not None and user.is_authenticated and not has_premium(user):
            limit = settings.FREE_TIER_URL_LIMIT
            if URL.objects.filter(owner_id=caller_id(user)).count() >= limit:
                raise serializers.ValidationError(
                    {'detail': f'Free accounts are limited to {limit} URLs. '
                               f'Upgrade to Premium for unlimited URLs.'}
                )
        return attrs

    def create(self, validated_data):
        tag_names = validated_data.pop('tags', [])
        url = super().create(validated_data)
        if tag_names:
            self._apply_tags(url, tag_names)
        return url


class URLUpdateSerializer(TagNamesMixin, serializers.ModelSerializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
    )

    class Meta:
        model = URL
        # `custom_alias` and `short_code` are deliberately not editable: both
        # are public addresses, and changing one silently breaks every link
        # already handed out.
        fields = ['original_url', 'title', 'description', 'is_active', 'expires_at', 'tags']

    def update(self, instance, validated_data):
        tag_names = validated_data.pop('tags', None)
        url = super().update(instance, validated_data)
        if tag_names is not None:
            self._apply_tags(url, tag_names)
        return url


class URLDetailSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()
    # An id, not a name: the user table is another service's and cannot be
    # joined to. Callers who need the username have it in their own token.
    owner_id = serializers.IntegerField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = URL
        fields = ['id', 'original_url', 'short_code', 'custom_alias', 'short_url', 'owner_id',
                  'tags', 'title', 'description', 'favicon', 'is_active', 'expires_at',
                  'click_count', 'created_at']

    def get_short_url(self, obj) -> str:
        request = self.context.get('request')
        code = obj.active_code
        if request:
            return request.build_absolute_uri(f'/{code}/')
        return f'/{code}/'
