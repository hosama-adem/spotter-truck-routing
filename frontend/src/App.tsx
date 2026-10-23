import { useState } from 'react'

import type { PlanResponse } from './api/types'
import { TripForm } from './components/TripForm'

function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)

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

      <TripForm
        onPlanned={(result) => {
          setPlan(result)
        }}
      />

      {plan ? (
        <section className="plan-ready" aria-live="polite">
          <h2>Plan ready</h2>
          <p>
            Recommended <strong>Route {plan.recommended_route_id}</strong>
            {' — '}
            {plan.recommendation_reason}
          </p>
          <p className="plan-ready-meta">
            {plan.routes.length} routes · map &amp; cards land in the next issue
          </p>
        </section>
      ) : null}
    </main>
  )
}

export default App
