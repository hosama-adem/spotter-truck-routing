"""Trip API views."""

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from trips.providers.geocode import PeliasGeocoder


def _geocoder() -> PeliasGeocoder:
    return PeliasGeocoder(api_key=settings.ORS_API_KEY)


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
