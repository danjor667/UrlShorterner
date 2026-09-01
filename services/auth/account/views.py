from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """Create a free-tier account and hand back a usable token pair."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'register'

    @extend_schema(summary='Register a new account', responses={201: UserSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = LoginSerializer.get_token(user)
        return Response(
            {
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Rate-limited credential exchange for an access/refresh pair."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'login'

    @extend_schema(summary='Obtain a JWT token pair')
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary='Refresh an access token')
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UpgradeView(APIView):
    """Move the caller onto the Premium tier and reissue their tokens.
    """

    throttle_scope = 'upgrade'

    @extend_schema(
        summary='Upgrade the current account to Premium (stands in for billing)',
        request=None,
        responses={200: UserSerializer},
    )
    def post(self, request):
        user = request.user

        # Idempotent: upgrading twice is not an error, it just reissues.
        if user.tier != User.Tier.PREMIUM:
            user.tier = User.Tier.PREMIUM
            user.save(update_fields=['tier'])

        refresh = LoginSerializer.get_token(user)
        return Response(
            {
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        )


class MeView(generics.RetrieveAPIView):
    """Who am I — handy for confirming a token and its tier."""

    serializer_class = UserSerializer

    @extend_schema(summary='Current user')
    def get_object(self):
        return self.request.user
