from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from shortener.urls import redirect_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/urls/', include('shortener.urls')),

    # Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Public redirect — must be last to avoid conflicts
urlpatterns += redirect_urlpatterns
