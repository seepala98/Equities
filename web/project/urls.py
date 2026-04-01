from django.contrib import admin
from django.urls import path, include

try:
    from .urls_local import urlpatterns as local_urls
except Exception:
    local_urls = []

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('stocks.api_urls')),
    path('', include('django_prometheus.urls')),
]

urlpatterns += local_urls
