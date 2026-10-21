# PRD — Weather-Aware Truck Routing

| Field | Value |
|---|---|
| Author | Hosama |
| Status | Approved for build |
| Version | 1.0 |
| Date | 2026-10-20 |
| Deadline | 4 days / max 16 work hours (target: ~13h) |
| Stack | Django + DRF (backend), React + TypeScript + Vite (frontend) |

---

## 1. Problem

Truck drivers pick routes by time alone. Weather along a route changes hour by hour, and heavy loads
are far more dangerous in high wind. Drivers need to see **which route is safest at the time they will
actually be on each road segment**, weighted against how long each route takes.

## 2. Goal

Given origin, destination, departure time and load weight, return **3 route options**, score each
for weather risk at the truck's **arrival time** at each checkpoint, **recommend the best one**, and
show everything on a map with a **0–48h weather heatmap**.

### Success criteria (how this is graded)

| Weight | Area | "Done well" means |
|---|---|---|
| 40% | Routes, weather, risk & recommendation logic | Rules implemented exactly, edge cases tested, ETAs drive weather lookups |
| 40% | UI, map & heatmap smoothness | Slider scrubs instantly (no network per tick), map never janks |
| 15% | Code quality | Small typed modules, pure risk engine, tests, CI green |
| 5% | Docs & walkthrough | Clear README + 5–10 min Loom |

## 3. User & core user story

**Persona:** Long-haul truck driver / dispatcher planning a trip.

> As a driver, I enter where I'm going, when I leave and how heavy my load is, so that I can pick the
> route that keeps me out of dangerous weather without wasting hours.

## 4. Functional requirements

### Inputs
| ID | Requirement |
|---|---|
| IN-1 | Origin and destination (text with autocomplete → lat/lon via geocoding API) |
| IN-2 | Departure date/time (local, sent to API as ISO-8601 with timezone) |
| IN-3 | Load weight in lb (validated: 1 – 80,000) |
| IN-4 | Checkpoint interval selector: **10 / 25 / 50 miles** (default 25) |

### Backend logic
| ID | Requirement |
|---|---|
| RT-1 | Fetch **3 route options** from a routing API (truck/HGV profile preferred). If the provider returns fewer than 3, generate alternatives via offset via-points so the user always sees 3 |
| RT-2 | Sample checkpoints along each route every N miles (N = IN-4), always including origin and destination |
| RT-3 | Compute each checkpoint's **ETA** = departure + cumulative routed duration to that point (interpolated from provider step durations, not constant speed) |
| WX-1 | Fetch hourly forecast for each checkpoint **at its ETA hour** (wind mph, rain in/hr, snowfall in/hr) |
| WX-2 | Batch weather requests and cache results (rounded lat/lon + hour, TTL 30 min) |
| RK-1 | Classify each checkpoint with the risk rules (§5); final level = worst of wind/rain/snow after load rules |
| RK-2 | Record *why* a checkpoint got its level (e.g. `["wind", "load"]`) for UI explanation |
| RC-1 | Rank routes with the recommendation order (§6) and return a human-readable reason |

### Frontend
| ID | Requirement |
|---|---|
| UI-1 | Map shows all 3 routes; recommended route highlighted, others dimmed; click a card or line to focus it |
| UI-2 | Checkpoints are color-coded by risk; popup shows mile, ETA, wind/rain/snow, level and reason |
| UI-3 | Route summary cards: distance, duration, ETA, miles by risk level, avg risk, "Recommended" badge + reason |
| UI-4 | Weather heatmap over the trip corridor with a **0–48h slider** (hour offset from departure) |
| UI-5 | Slider scrubbing is instant: all 49 hours are loaded once, slider only swaps the rendered frame |
| UI-6 | Loading, empty and error states (geocode not found, no route, weather API down) |

## 5. Risk rules (source of truth)

Levels are ordinal: `LOW=0, MODERATE=1, HIGH=2, SEVERE=3, NO_TRAVEL=4`.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25 ≤ x < 35 | 35 ≤ x < 45 | 45 ≤ x < 55 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10 ≤ x < 0.25 | 0.25 ≤ x < 0.50 | 0.50 ≤ x ≤ 1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5 ≤ x < 1.0 | 1.0 ≤ x < 2.0 | 2.0 ≤ x ≤ 3.0 | > 3.0 |

**Load rules** (applied to wind, can only raise the level):
1. Wind ≥ 55 mph → `NO_TRAVEL` for any load
2. Wind 45–54 mph **and** load > 30,000 lb → `NO_TRAVEL`
3. Wind 35–44 mph **and** load > 40,000 lb → `SEVERE`

**Final checkpoint level** = `max(wind_level_after_load_rules, rain_level, snow_level)`.

## 6. Recommendation logic

**Miles per level:** the road segment between two consecutive checkpoints is assigned the **worse** of
its two endpoint levels (conservative = safety-first). Summing segment lengths gives miles per level.

**Average risk** = mile-weighted mean of segment levels (0–4).

**Ranking** (lexicographic, ascending):
```
(no_travel_miles, severe_miles, high_miles, avg_risk, duration_seconds)
```
The spec lists Severe first. `NO_TRAVEL` is strictly worse than Severe, so it is ranked ahead of it.
This is a documented assumption (§9).

**Reason string** example: *"Route B recommended: 0 severe mi vs 42 on Route A; only 18 min slower."*

## 7. API contract (v1)

```
GET  /api/health
GET  /api/geocode?q=<text>                    -> [{label, lat, lon}]
POST /api/trips/plan                          -> routes + checkpoints + recommendation
POST /api/weather/heatmap                     -> corridor grid x 49 hours
```

`POST /api/trips/plan` request:
```json
{
  "origin": {"lat": 41.88, "lon": -87.63, "label": "Chicago, IL"},
  "destination": {"lat": 39.74, "lon": -104.99, "label": "Denver, CO"},
  "departure_time": "2026-10-21T06:00:00-05:00",
  "load_weight_lb": 42000,
  "checkpoint_interval_mi": 25
}
```

Response (shape):
```json
{
  "recommended_route_id": "B",
  "recommendation_reason": "string",
  "routes": [{
    "id": "B", "rank": 1,
    "geometry": {"type": "LineString", "coordinates": [[-87.63, 41.88]]},
    "summary": {
      "distance_mi": 1003.2, "duration_s": 54000, "arrival_time": "ISO",
      "miles_by_level": {"LOW": 900, "MODERATE": 80, "HIGH": 23, "SEVERE": 0, "NO_TRAVEL": 0},
      "avg_risk": 0.12, "max_level": "HIGH"
    },
    "checkpoints": [{
      "mile": 25.0, "lat": 41.7, "lon": -88.1, "eta": "ISO",
      "weather": {"wind_mph": 18, "gust_mph": 27, "rain_in_hr": 0.02, "snow_in_hr": 0},
      "risk": {"level": "LOW", "score": 0, "drivers": []}
    }]
  }]
}
```

`POST /api/weather/heatmap` returns compact arrays (fast to transfer and render):
```json
{ "start_time": "ISO", "hours": 49,
  "points": [[lon, lat], ...],
  "risk":   [[0,1,0,...], ...]   // risk[hour][point_index], 0–4
}
```

## 8. Technical approach

| Concern | Choice | Why |
|---|---|---|
| Routing | OpenRouteService `driving-hgv` (alt: Mapbox Directions) behind a `RoutingProvider` interface | Truck profile + alternatives; swappable if limits bite |
| Geocoding | Same provider's geocoder (or Photon) | One key, autocomplete |
| Weather | Open-Meteo hourly forecast (`wind_speed_10m`, `wind_gusts_10m`, `rain`, `showers`, `snowfall`, `wind_speed_unit=mph`, `precipitation_unit=inch`) | Free, no key, multi-location batch in one call |
| Map | MapLibre GL + react-map-gl + deck.gl (`PathLayer`, `ScatterplotLayer`, `HeatmapLayer`) | GPU rendering = smooth heatmap |
| Data fetching | TanStack Query | Caching, loading/error states for free |
| Backend cache | Django cache (locmem → Redis if available) | Avoid duplicate weather calls |
| Tests | pytest (backend), Vitest (frontend utils) | Risk engine 100% covered |
| CI | GitHub Actions: ruff + pytest; eslint + tsc + build | Shows code-quality discipline |
| Hosting | Frontend on Vercel, backend on Render/Railway | Free tiers, quick deploys |

**Backend module layout** (pure logic separated from I/O):
```
backend/trips/
  providers/routing.py   # RoutingProvider interface + ORS impl
  providers/weather.py   # Open-Meteo client (batched, cached)
  domain/sampling.py     # checkpoints + ETA interpolation   (pure)
  domain/risk.py         # thresholds + load rules            (pure)
  domain/ranking.py      # miles-by-level, avg, sort, reason  (pure)
  services.py            # orchestrates the plan
  views.py / serializers.py
```

## 9. Assumptions (also listed in README)

1. Wind classification uses **sustained** wind (`wind_speed_10m`); gusts are shown for context only.
2. Rain = `rain + showers` (hourly sum ≈ in/hr). Snow = `snowfall` (hourly, inches).
3. Weather is read for the forecast hour **nearest** to each checkpoint ETA.
4. Heatmap slider hour 0 = departure time; covers departure + 0…48h.
5. `NO_TRAVEL` ranks worse than `SEVERE` (§6).
6. ETAs come from the routing provider's durations; no driver breaks (Hours-of-Service) are modelled.
7. Checkpoints with an ETA beyond the forecast range are marked `NO_DATA` and excluded from averages.

## 10. Non-goals

Auth/accounts, saved trips, live traffic, HOS break planning, bridge/height restrictions beyond the
provider's HGV profile, mobile app, our own routing engine.

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Routing API returns < 3 alternatives or has distance limits on alternatives | Spike on day 1; via-point fallback generator; provider interface allows swap |
| Weather API rate limits | Batch multi-location calls, round coords to ~0.1°, cache |
| Heatmap slow on long trips | Cap corridor grid (~300 pts), precompute 49 frames, GPU layer, no refetch on slide |
| Timezone bugs in ETAs | Store/compute in UTC, convert only for display; tests with DST |
| Free-tier backend cold start | Health ping before Loom recording; README note |

## 12. Milestones

| M | Deliverable | Est. |
|---|---|---|
| M1 | Skeleton deployed (backend + frontend talking, CI green) | 2h |
| M2 | Routes + checkpoints + ETAs via API | 2.5h |
| M3 | Weather + risk engine + ranking (fully tested) | 3h |
| M4 | Map UI, route cards, checkpoint popups | 2.5h |
| M5 | Heatmap + 0–48h slider, performance pass | 2h |
| M6 | README, final deploy, Loom | 1h |
