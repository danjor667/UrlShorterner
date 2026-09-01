from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Safe representation of a user — never exposes the password hash."""

    has_premium_access = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'tier', 'is_premium', 'has_premium_access', 'date_joined']
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        # Run Django's validators against a throwaway instance so the
        # UserAttributeSimilarityValidator can see the username/email.
        candidate = User(username=attrs['username'], email=attrs['email'])
        validate_password(attrs['password'], user=candidate)
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        # Tier is never client-settable: everyone registers on the free tier.
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    """Puts everything downstream services need into the token itself.

    The shortener and analytics services have no user table to look anything up
    in, so each claim here is load-bearing: `is_premium` gates analytics,
    `is_staff` lets ownership checks be overridden, and `username` is the only
    way either service can name an owner. Adding a claim is a deploy of this
    service; *relying* on a new one is a deploy of the other two.

    `is_premium` carries `has_premium_access`, not the raw column, so the ADMIN
    tier reaches downstream gates as premium.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['tier'] = user.tier
        token['is_premium'] = user.has_premium_access
        token['username'] = user.username
        token['is_staff'] = user.is_staff
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
