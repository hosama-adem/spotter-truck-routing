"""Trip API views."""

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from trips.providers.geocode import PeliasGeocoder
from trips.providers.routing import LatLon, OpenRouteServiceProvider
from trips.providers.weather import OpenMeteoWeatherClient
from trips.serializers import PlanTripSerializer
from trips.services import PlanInput, plan_trip


def _geocoder() -> PeliasGeocoder:
    return PeliasGeocoder(api_key=settings.ORS_API_KEY)


def _router() -> OpenRouteServiceProvider:
    return OpenRouteServiceProvider(api_key=settings.ORS_API_KEY)


def _weather() -> OpenMeteoWeatherClient:
    return OpenMeteoWeatherClient()


def _parse_float(raw: str | None, name: str) -> float:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"Query parameter {name} is required.")
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Query parameter {name} must be a number.") from exc


def _parse_lat_lon(
    *,
    lat_raw: str | None,
    lon_raw: str | None,
    lat_name: str,
    lon_name: str,
) -> LatLon:
    lat = _parse_float(lat_raw, lat_name)
    lon = _parse_float(lon_raw, lon_name)
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Query parameter {lat_name} must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Query parameter {lon_name} must be between -180 and 180.")
    return LatLon(lat=lat, lon=lon)


@api_view(["GET"])
def geocode(request: Request) -> Response:
    query = (request.query_params.get("q") or "").strip()
    if not query:
        return Response(
            {"detail": "Query parameter q is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not settings.ORS_API_KEY:
        return Response(
            {"detail": "Geocoding is not configured (missing ORS_API_KEY)."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        results = _geocoder().autocomplete(query, limit=5)
    except RuntimeError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response([item.as_dict() for item in results])


@api_view(["GET"])
def routes(request: Request) -> Response:
    """Return exactly three truck route options for an OD pair."""
    try:
        origin = _parse_lat_lon(
            lat_raw=request.query_params.get("origin_lat"),
            lon_raw=request.query_params.get("origin_lon"),
            lat_name="origin_lat",
            lon_name="origin_lon",
        )
        destination = _parse_lat_lon(
            lat_raw=request.query_params.get("dest_lat"),
            lon_raw=request.query_params.get("dest_lon"),
            lat_name="dest_lat",
            lon_name="dest_lon",
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if origin == destination:
        return Response(
            {"detail": "Origin and destination must be different points."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not settings.ORS_API_KEY:
        return Response(
            {"detail": "Routing is not configured (missing ORS_API_KEY)."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        options = _router().fetch_routes(origin, destination)
    except RuntimeError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if len(options) != 3:
        return Response(
            {"detail": f"Expected 3 routes, got {len(options)}."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({"routes": [route.as_dict() for route in options]})


@api_view(["POST"])
def plan(request: Request) -> Response:
    """Plan three truck routes with weather risk and a recommendation."""
    serializer = PlanTripSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    if not settings.ORS_API_KEY:
        return Response(
            {"detail": "Routing is not configured (missing ORS_API_KEY)."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    plan_input = PlanInput(
        origin=LatLon(lat=data["origin"]["lat"], lon=data["origin"]["lon"]),
        destination=LatLon(
            lat=data["destination"]["lat"],
            lon=data["destination"]["lon"],
        ),
        departure_time=data["departure_time"],
        load_weight_lb=data["load_weight_lb"],
        checkpoint_interval_mi=data["checkpoint_interval_mi"],
    )

    try:
        payload = plan_trip(plan_input, router=_router(), weather=_weather())
    except RuntimeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(payload)

