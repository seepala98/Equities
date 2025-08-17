from django.contrib import admin
from django.urls import path

try:
    from .urls_local import urlpatterns as local_urls
except Exception:
    local_urls = []

urlpatterns = [
    path('admin/', admin.site.urls),
]

urlpatterns += local_urls
