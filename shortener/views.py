from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from .models import URL
from .serializers import URLCreateSerializer, URLDetailSerializer


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
    queryset = URL.objects.filter(is_active=True)
    serializer_class = URLDetailSerializer

    @extend_schema(summary="List all active short URLs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class URLRedirectView(APIView):
    @extend_schema(exclude=True)
    def get(self, request, short_code):
        url = get_object_or_404(URL, is_active=True, short_code=short_code) if not URL.objects.filter(
            custom_alias=short_code, is_active=True).exists() else URL.objects.get(custom_alias=short_code, is_active=True)

        if url.expires_at and url.expires_at < timezone.now():
            return Response({'error': 'This URL has expired.'}, status=status.HTTP_410_GONE)

        url.click_count += 1
        url.save(update_fields=['click_count'])
        return HttpResponseRedirect(url.original_url)
