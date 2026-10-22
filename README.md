# Weather-Aware Truck Routing

[![CI](https://github.com/hosama-adem/spotter-truck-routing/actions/workflows/ci.yml/badge.svg)](https://github.com/hosama-adem/spotter-truck-routing/actions/workflows/ci.yml)

## Live

- App: https://spotter-truck-routing.vercel.app
- API health: https://spotter-truck-routing-api.onrender.com/api/health

The free Render service sleeps when idle. The first health call after that can take about a minute.

Day-1 skeleton: a Django + DRF API and a Vite + React + TypeScript client.
Requirements are in [docs/PRD.md](docs/PRD.md). Weather, risk, ranking, and the map are not built yet; routing provider choice is below.

## Decisions

**Routing provider: OpenRouteService `driving-hgv`** via `https://api.heigit.org/openrouteservice` (not the deprecated `api.openrouteservice.org` host).

| Finding | Impact |
|---|---|
| Free Standard quota | Directions ~2000/day, ~40/min — enough for demos and CI-mocked work |
| Truck profile | `driving-hgv` with optional HGV restrictions later |
| Single route distance | Public API allows up to **6,000 km** — Chicago → Denver is fine |
| Native alternatives | Cap is **3** routes, but only for OD pairs ≤ **100 km** |
| Long-haul (our PRD OD) | Native `alternative_routes` will not cover Chicago → Denver |

**How we always return 3 routes:** for trips longer than 100 km (and as a fallback when alternatives return fewer than 3), request three separate `driving-hgv` routes: direct, plus left/right mid-corridor via-points (~40 mi perpendicular offset). The `RoutingProvider` interface in `backend/trips/providers/routing.py` keeps Mapbox Directions as a future swap if ORS limits bite harder.

Live check (optional): put a free key from [account.heigit.org](https://account.heigit.org/) in `backend/.env` as `ORS_API_KEY`, then run `backend/.venv/Scripts/python backend/scripts/spike_routing.py`.

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
  trips/providers/       RoutingProvider + ORS client; weather later
  scripts/spike_routing.py   optional live ORS check
frontend/                Vite + React + TypeScript
```
