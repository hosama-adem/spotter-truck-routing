import { useEffect, useState } from 'react'

import { ApiError } from './api/client'
import { fetchHeatmap } from './api/heatmap'
import type { HeatmapResponse, PlanResponse, TripPlanContext } from './api/types'
import { RouteCards } from './components/RouteCards'
import { TripForm } from './components/TripForm'
import { TripMap } from './components/TripMap'

function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [tripContext, setTripContext] = useState<TripPlanContext | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null)
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [heatmapError, setHeatmapError] = useState<string | null>(null)
  const [hour, setHour] = useState(0)

  const activeRouteId = selectedRouteId ?? plan?.recommended_route_id ?? null

  useEffect(() => {
    if (!plan || !tripContext) {
      return
    }
    const recommended = plan.routes.find(
      (route) => route.id === plan.recommended_route_id,
    )
    if (!recommended) {
      return
    }

    const controller = new AbortController()

    fetchHeatmap(
      {
        departure_time: tripContext.departure_time,
        load_weight_lb: tripContext.load_weight_lb,
        geometry: recommended.geometry,
      },
      controller.signal,
    )
      .then((payload) => {
        setHeatmap(payload)
        setHeatmapError(null)
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        setHeatmap(null)
        setHeatmapError(
          err instanceof ApiError
            ? err.message
            : 'Could not load corridor heatmap.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setHeatmapLoading(false)
        }
      })

    return () => controller.abort()
  }, [plan, tripContext])

  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="brand">Spotter</p>
        <h1>Weather-Aware Truck Routing</h1>
        <p className="lede">
          Rank three HGV corridors by forecast risk at the time your truck arrives — not by weather
          right now.
        </p>
      </header>

      <div className={plan ? 'workspace has-plan' : 'workspace'}>
        <div className="workspace-form">
          <TripForm
            onPlanned={(result, context) => {
              setPlan(result)
              setTripContext(context)
              setSelectedRouteId(result.recommended_route_id)
              setHeatmap(null)
              setHeatmapError(null)
              setHour(0)
              setHeatmapLoading(true)
            }}
          />
        </div>

        {plan && activeRouteId ? (
          <div className="workspace-results">
            <TripMap
              key={plan.recommended_route_id + plan.routes.map((r) => r.id).join('')}
              plan={plan}
              selectedRouteId={activeRouteId}
              onSelectRoute={setSelectedRouteId}
              heatmap={heatmap}
              heatmapLoading={heatmapLoading}
              heatmapError={heatmapError}
              hour={hour}
              onHourChange={setHour}
            />
            <RouteCards
              plan={plan}
              selectedRouteId={activeRouteId}
              onSelect={setSelectedRouteId}
            />
          </div>
        ) : null}
      </div>
    </main>
  )
}

export default App
