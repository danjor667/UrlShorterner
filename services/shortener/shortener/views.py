import logging

from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .analytics_client import AnalyticsUnavailable, record_click
from .models import URL
from .serializers import URLCreateSerializer, URLDetailSerializer

logger = logging.getLogger(__name__)


class URLCreateView(generics.CreateAPIView):
    queryset = URL.objects.all()
    serializer_class = URLCreateSerializer

    @extend_schema(
        summary="Create a short URL",
        responses={201: URLDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.save()
        response_serializer = URLDetailSerializer(url, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class URLListView(generics.ListAPIView):
    queryset = URL.objects.active_urls().with_related()
    serializer_class = URLDetailSerializer

    @extend_schema(summary="List all active short URLs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class URLRedirectView(APIView):
    @extend_schema(exclude=True)
    def get(self, request, short_code):
        url = get_object_or_404(URL.objects.get_queryset().for_code(short_code), is_active=True)

        if url.is_expired:
            return Response({'error': 'This URL has expired.'}, status=status.HTTP_410_GONE)

        # Analytics first, and only then the local counter. Doing it in this
        # order means click_count can never claim a click that analytics has
        # no row for; the reverse order would drift on every failure.
        try:
            record_click(url.pk, request)
        except AnalyticsUnavailable as exc:
            logger.error('click not recorded for url %s: %s', url.pk, exc)
            return Response(
                {'error': 'Click tracking is unavailable, so the redirect was not served.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        URL.objects.filter(pk=url.pk).update(click_count=F('click_count') + 1)
        return HttpResponseRedirect(url.original_url)
