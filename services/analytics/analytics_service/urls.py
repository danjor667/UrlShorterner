from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # See auth_service/urls.py — each service's admin gets its own prefix.
    path('admin/analytics/', admin.site.urls),

    # Service-to-service only. The gateway returns 404 for /internal/ so this
    # is reachable from inside the compose network and nowhere else. Module 7
    # adds a shared-secret header; today the network boundary is the control.
    path('internal/', include('analytics.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
