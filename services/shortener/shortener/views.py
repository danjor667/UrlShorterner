import logging

from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsOwnerOrReadOnly, caller_id

from .analytics_client import AnalyticsUnavailable, record_click
from .models import URL
from .serializers import URLCreateSerializer, URLDetailSerializer, URLUpdateSerializer

logger = logging.getLogger(__name__)


class URLCreateView(generics.CreateAPIView):
    queryset = URL.objects.all()
    serializer_class = URLCreateSerializer
    throttle_scope = 'create_short_code'

    @extend_schema(
        summary="Create a short URL",
        responses={201: URLDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # `owner_id` is never accepted from the client — it is not a writable
        # field on the serializer. It comes from the token and nowhere else.
        url = serializer.save(owner_id=caller_id(request.user))
        response_serializer = URLDetailSerializer(url, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class URLListView(generics.ListAPIView):
    serializer_class = URLDetailSerializer

    def get_queryset(self):
        """Callers only ever see their own URLs."""
        return (
            URL.objects.active_urls()
            .filter(owner_id=caller_id(self.request.user))
            .with_related()
        )

    @extend_schema(summary="List your active short URLs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class URLDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a single URL, addressed by code or alias."""

    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    lookup_url_kwarg = 'short_code'

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return URLUpdateSerializer
        return URLDetailSerializer

    def get_object(self):
        code = self.kwargs[self.lookup_url_kwarg]
        url = get_object_or_404(URL.objects.get_queryset().for_code(code).with_related())
        # Not optional. DRF's automatic object-permission check lives inside
        # the base `get_object` this overrides, so without this line every
        # ownership check silently stops running.
        self.check_object_permissions(self.request, url)
        return url

    @extend_schema(summary="Retrieve a short URL", responses={200: URLDetailSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Update a short URL you own", responses={200: URLDetailSerializer})
    def update(self, request, *args, **kwargs):
        """Write with the update serializer, but answer with the detail one."""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False)
        )
        serializer.is_valid(raise_exception=True)
        url = serializer.save()
        return Response(URLDetailSerializer(url, context={'request': request}).data)

    @extend_schema(summary="Delete a short URL you own")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class URLRedirectView(APIView):
    """The public entry point — the one endpoint that stays anonymous.

    Both attributes below are load-bearing as of Module 7. The service-wide
    default is now `IsAuthenticated` with JWT authentication, so without them a
    plain `GET /abc123` would 401 — and a stray `Authorization` header on a
    short link would be parsed and rejected rather than ignored.
    """

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(exclude=True)
    def get(self, request, short_code):
        url = get_object_or_404(URL.objects.get_queryset().for_code(short_code), is_active=True)

        if url.is_expired:
            return Response({'error': 'This URL has expired.'}, status=status.HTTP_410_GONE)

        try:
            record_click(url.pk, request)
        except AnalyticsUnavailable as exc:
            logger.error(
                'click lost for url %s — analytics unreachable: %s', url.pk, exc
            )

        URL.objects.filter(pk=url.pk).update(click_count=F('click_count') + 1)
        return HttpResponseRedirect(url.original_url)
