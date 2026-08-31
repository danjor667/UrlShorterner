from drf_spectacular.utils import extend_schema
from rest_framework import generics

from .models import Click
from .serializers import ClickCreateSerializer


class ClickCreateView(generics.CreateAPIView):
    """Record one click. Called by the shortener, not by the public.

    The shortener blocks on this: if it fails, the redirect fails rather than
    silently losing the event. That makes this endpoint part of the critical
    path for every short link, so it stays deliberately small — one insert,
    no lookups, no joins.
    """

    queryset = Click.objects.all()
    serializer_class = ClickCreateSerializer

    @extend_schema(summary="Record a click (internal)")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
