from django.urls import path
from .views import URLCreateView, URLListView, URLRedirectView

urlpatterns = [
    path('', URLListView.as_view(), name='url-list'),
    path('create/', URLCreateView.as_view(), name='url-create'),
]

redirect_urlpatterns = [
    path('<str:short_code>/', URLRedirectView.as_view(), name='url-redirect'),
]
