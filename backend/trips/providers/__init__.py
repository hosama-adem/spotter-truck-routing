"""External routing and weather clients."""

from trips.providers.geocode import GeocodeProvider, GeocodeResult, PeliasGeocoder
from trips.providers.routing import (
    LatLon,
    OpenRouteServiceProvider,
    RouteOption,
    RoutingProvider,
)
from trips.providers.weather import (
    OpenMeteoWeatherClient,
    WeatherProvider,
    WeatherQuery,
    WeatherSample,
)

__all__ = [
    "GeocodeProvider",
    "GeocodeResult",
    "LatLon",
    "OpenMeteoWeatherClient",
    "OpenRouteServiceProvider",
    "PeliasGeocoder",
    "RouteOption",
    "RoutingProvider",
    "WeatherProvider",
    "WeatherQuery",
    "WeatherSample",
]
