# Weather-Aware Truck Routing

[![CI](https://github.com/hosama-adem/spotter-truck-routing/actions/workflows/ci.yml/badge.svg)](https://github.com/hosama-adem/spotter-truck-routing/actions/workflows/ci.yml)

## Live

- App: https://spotter-truck-routing.vercel.app
- API health: https://spotter-truck-routing-api.onrender.com/api/health

The free Render service sleeps when idle. The first health call after that can take about a minute.

Day-1 skeleton: a Django + DRF API and a Vite + React + TypeScript client.
Requirements are in [docs/PRD.md](docs/PRD.md). Weather, risk, ranking, and the map are not built yet.

## Decisions

**Routing provider: OpenRouteService `driving-hgv`** via `https://api.heigit.org/openrouteservice`.

| Finding | Impact |
|---|---|
| Free Standard quota | Directions ~2000/day, ~40/min |
| Truck profile | `driving-hgv` |
| Single route distance | Up to **6,000 km** on the public API |
| Native alternatives | Max **3**, but only for OD pairs ≤ **100 km** |
| Long-haul (Chicago → Denver) | Use via-point requests, not native alternatives |

**How we always return 3 routes:** long trips (and short trips that return fewer than 3 alternatives) request three `driving-hgv` corridors — direct, plus left/right mid-corridor vias (~40 mi offset). API: `GET /api/routes?origin_lat=&origin_lon=&dest_lat=&dest_lon=`. The `RoutingProvider` interface keeps Mapbox as a future swap.

## Run locally

Python 3.10+ and Node.js 20.19+ (or 22.12+). Four commands from the repo root. Steps 2 and 3 use the Windows virtualenv path; on macOS or Linux, swap `Scripts/python` for `bin/python`.

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt && backend/.venv/Scripts/python backend/manage.py migrate
backend/.venv/Scripts/python backend/manage.py runserver
cd frontend && npm install && npm run dev
```

Leave the API and the Vite dev server running. The API is at http://127.0.0.1:8000 and the app is at http://localhost:5173.

`GET /api/health` returns `200` and `{"status":"ok"}`. The page calls that URL on load.

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env` only when you need to override the defaults (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `VITE_API_BASE_URL`).

## Layout

```
backend/                 Django project (config) and the trips app
  trips/domain/          sampling, risk, ranking (later; pure)
  trips/providers/       geocode + RoutingProvider / ORS client
frontend/                Vite + React + TypeScript
```
