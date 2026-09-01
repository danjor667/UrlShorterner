from django.urls import path

from .views import (
    AnalyticsView, ClickCreateView, URLProjectionDeleteView, URLProjectionUpsertView,
)

# Service-to-service only; the gateway returns 404 for /internal/.
internal_urlpatterns = [
    path('clicks/', ClickCreateView.as_view(), name='click-create'),
    path('urls/', URLProjectionUpsertView.as_view(), name='projection-upsert'),
    path('urls/<int:url_id>/', URLProjectionDeleteView.as_view(), name='projection-delete'),
]

# Public, behind the gateway at /api/v1/analytics/.
urlpatterns = [
    path('<str:short_code>/', AnalyticsView.as_view(), name='url-analytics'),
]
