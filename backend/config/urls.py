from django.contrib import admin
from django.urls import path

from config.health import health
from trips.views import geocode, heatmap, plan, routes

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/health/", health),
    path("api/geocode", geocode),
    path("api/geocode/", geocode),
    path("api/routes", routes),
    path("api/routes/", routes),
    path("api/trips/plan", plan),
    path("api/trips/plan/", plan),
    path("api/weather/heatmap", heatmap),
    path("api/weather/heatmap/", heatmap),
]
