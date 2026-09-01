from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPremium, caller_id

from .models import Click, URLProjection
from .serializers import (
    AnalyticsSerializer, ClickCreateSerializer, ClickSerializer, URLProjectionSerializer,
)


class ClickCreateView(generics.CreateAPIView):
    """Record one click. Called by the shortener, not by the public.

    """

    queryset = Click.objects.all()
    serializer_class = ClickCreateSerializer

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Record a click (internal)")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class URLProjectionUpsertView(APIView):
    """Accept the shortener's copy of a URL, or drop it.
    """

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Upsert a URL projection (internal)")
    def post(self, request):
        serializer = URLProjectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Copy before popping: `validated_data` is what the serializer renders
        # itself from, so mutating it in place makes the response blow up.
        fields = dict(serializer.validated_data)
        projection, created = URLProjection.objects.update_or_create(
            url_id=fields.pop('url_id'), defaults=fields
        )
        return Response(
            URLProjectionSerializer(projection).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class URLProjectionDeleteView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Delete a URL projection (internal)")
    def delete(self, request, url_id):
        deleted, _ = URLProjection.objects.filter(url_id=url_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # The clicks outlive the URL on purpose: deleting a short link should
        # not rewrite the history of what happened while it existed.
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnalyticsView(APIView):
    """Premium-only click analytics for a URL you own.
    """

    permission_classes = [permissions.IsAuthenticated, IsPremium]

    RECENT_CLICK_LIMIT = 20

    @extend_schema(summary="Click analytics (Premium)", responses={200: AnalyticsSerializer})
    def get(self, request, short_code):
        url = get_object_or_404(URLProjection.for_code(short_code))

        if url.owner_id != caller_id(request.user) and not request.user.is_staff:
            raise PermissionDenied('You do not own this URL.')

        clicks = Click.objects.filter(url_id=url.url_id)
        by_country = (
            clicks.exclude(country='')
            .values('country')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        payload = {
            'short_code': url.active_code,
            'original_url': url.original_url,
            'total_clicks': clicks.count(),
            'unique_visitors': clicks.exclude(ip_address__isnull=True)
                                     .values('ip_address').distinct().count(),
            'clicks_by_country': {row['country']: row['total'] for row in by_country},
            'recent_clicks': ClickSerializer(clicks[:self.RECENT_CLICK_LIMIT], many=True).data,
        }
        return Response(AnalyticsSerializer(payload).data)
