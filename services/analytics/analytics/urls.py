from django.urls import path

from .views import ClickCreateView

urlpatterns = [
    path('clicks/', ClickCreateView.as_view(), name='click-create'),
]
