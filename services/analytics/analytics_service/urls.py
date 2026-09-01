from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from analytics.urls import internal_urlpatterns

urlpatterns = [
    # See auth_service/urls.py — each service's admin gets its own prefix.
    path('admin/analytics/', admin.site.urls),


    path('internal/', include((internal_urlpatterns, 'internal'))),


    path('api/v1/analytics/', include('analytics.urls')),


    path('api/schema/analytics/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/analytics/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
