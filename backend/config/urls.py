from django.contrib import admin
from django.urls import path

from config.health import health
from trips.views import geocode

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/health/", health),
    path("api/geocode", geocode),
    path("api/geocode/", geocode),
]
