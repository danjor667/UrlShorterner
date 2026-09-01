from django.urls import path

from .views import URLCreateView, URLDetailView, URLListView, URLRedirectView

urlpatterns = [
    path('', URLListView.as_view(), name='url-list'),
    path('create/', URLCreateView.as_view(), name='url-create'),
    # Must come after `create/`, or the literal would be read as a short code.
    path('<str:short_code>/', URLDetailView.as_view(), name='url-detail'),
]

redirect_urlpatterns = [
    path('<str:short_code>/', URLRedirectView.as_view(), name='url-redirect'),
]
