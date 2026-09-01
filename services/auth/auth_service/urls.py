from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/auth/', admin.site.urls),


    path('api/v1/auth/', include('account.urls')),


    path('api/schema/auth/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/auth/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
