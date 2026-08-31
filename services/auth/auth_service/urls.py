from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Mounted under a service-specific prefix, not the bare `admin/`. Three
    # services each have an admin and only one can own a path behind the
    # gateway; nginx routes by longest prefix, so `/admin/auth/` reaches here
    # while `/admin/` still reaches the shortener.
    path('admin/auth/', admin.site.urls),

    # No `api/v1/auth/` routes yet — registration and login are Module 7. The
    # gateway already points that prefix here so adding them changes no infra.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
