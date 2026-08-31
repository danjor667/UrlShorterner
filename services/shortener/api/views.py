from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from shortener.models import URL

from .serializers import URLCreateSerializer, URLDetailSerializer


class URLCreateView(generics.CreateAPIView):
    queryset = URL.objects.all()
    serializer_class = URLCreateSerializer

    @extend_schema(
        summary="Create a short URL",
        responses={201: URLDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        """Write with the create serializer, but answer with the detail one.

        The caller needs the generated `short_code` back, and that is not a
        field they were allowed to send.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.save()
        return Response(
            URLDetailSerializer(url, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class URLListView(generics.ListAPIView):
    queryset = URL.objects.filter(is_active=True)
    serializer_class = URLDetailSerializer

    @extend_schema(summary="List all active short URLs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class URLRedirectView(APIView):
    """The public entry point — no authentication, and none to add until Module 7."""

    @extend_schema(exclude=True)
    def get(self, request, short_code):
        # One query for both columns: a code may be either a generated
        # short_code or someone's custom alias.
        url = get_object_or_404(
            URL.objects.filter(Q(short_code=short_code) | Q(custom_alias=short_code)),
            is_active=True,
        )

        if url.expires_at and url.expires_at <= timezone.now():
            return Response({'error': 'This URL has expired.'}, status=status.HTTP_410_GONE)

        # F() rather than read-modify-write: two concurrent redirects would
        # otherwise each read the same count and one increment would be lost.
        URL.objects.filter(pk=url.pk).update(click_count=F('click_count') + 1)
        return HttpResponseRedirect(url.original_url)
