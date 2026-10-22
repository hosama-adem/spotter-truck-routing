"""Live ORS spike for playbook issue 4.

Usage (from repo root, with ORS_API_KEY in backend/.env or the environment):

  backend/.venv/Scripts/python backend/scripts/spike_routing.py
  backend/.venv/Scripts/python backend/scripts/spike_routing.py --short
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from trips.providers.routing import (  # noqa: E402
    ORS_ALTERNATIVES_MAX_DISTANCE_M,
    LatLon,
    OpenRouteServiceProvider,
    haversine_m,
)


def _load_dotenv() -> None:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _print_routes(label: str, origin: LatLon, destination: LatLon, routes: list) -> None:
    print(f"\n== {label} ==")
    print(f"haversine_km={haversine_m(origin, destination) / 1000:.1f}")
    print(f"routes_returned={len(routes)}")
    for route in routes:
        via = (
            f" via=({route.via.lat:.4f},{route.via.lon:.4f})"
            if route.via is not None
            else " via=direct"
        )
        print(
            f"  {route.id}: "
            f"{route.distance_m / 1609.344:.1f} mi, "
            f"{route.duration_s / 3600:.1f} h, "
            f"points={len(route.geometry)}{via}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike ORS driving-hgv for 3 truck routes")
    parser.add_argument(
        "--short",
        action="store_true",
        help="Use a short OD pair where native alternatives may work (≤ 100 km)",
    )
    args = parser.parse_args()
    _load_dotenv()

    api_key = os.environ.get("ORS_API_KEY", "").strip()
    if not api_key:
        print(
            "Set ORS_API_KEY in backend/.env (free key from https://account.heigit.org/).\n"
            "Without a key, the offline decision still stands: see README Decisions."
        )
        return 1

    provider = OpenRouteServiceProvider(api_key)

    if args.short:
        # Heidelberg area — short enough for alternative_routes on the public API.
        origin = LatLon(lat=49.41461, lon=8.681495)
        destination = LatLon(lat=49.420318, lon=8.687872)
        label = "short OD (native alternatives path)"
    else:
        origin = LatLon(lat=41.88, lon=-87.63)
        destination = LatLon(lat=39.74, lon=-104.99)
        label = "Chicago → Denver (via-point path expected)"

    print(f"alternatives_cap_km={ORS_ALTERNATIVES_MAX_DISTANCE_M / 1000:.0f}")
    routes = provider.fetch_routes(origin, destination)
    _print_routes(label, origin, destination, routes)

    if len(routes) < 3:
        print("\nWARNING: fewer than 3 routes. Tighten via offsets or swap provider.")
        return 2

    print("\nOK: provider returned 3 corridors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
