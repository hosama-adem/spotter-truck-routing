import { useState } from 'react'

import type { PlanResponse } from './api/types'
import { RouteCards } from './components/RouteCards'
import { TripForm } from './components/TripForm'
import { TripMap } from './components/TripMap'

function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)

  const activeRouteId = selectedRouteId ?? plan?.recommended_route_id ?? null

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
            onPlanned={(result: PlanResponse) => {
              setPlan(result)
              setSelectedRouteId(result.recommended_route_id)
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
