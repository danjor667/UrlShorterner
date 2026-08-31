from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from api.urls import redirect_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/v1/urls/', include('api.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Public redirect — must stay last, it matches any single path segment and
# would otherwise swallow every route above it.
urlpatterns += redirect_urlpatterns
