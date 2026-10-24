import type { PlanResponse, PlannedRoute, RiskLevel } from '../api/types'
import {
  formatDistanceMi,
  formatDuration,
  formatEta,
  formatMilesByLevel,
} from '../lib/format'
import { RISK_COLORS, RISK_LABELS, RISK_LEVELS } from '../lib/riskColors'

type RouteCardsProps = {
  plan: PlanResponse
  selectedRouteId: string
  onSelect: (routeId: string) => void
}

export function RouteCards({ plan, selectedRouteId, onSelect }: RouteCardsProps) {
  const sorted = [...plan.routes].sort((a, b) => a.rank - b.rank)

  return (
    <section className="route-cards" aria-label="Route options">
      <header className="route-cards-header">
        <h2>Route options</h2>
        <p>{plan.recommendation_reason}</p>
      </header>
      <div className="route-cards-list">
        {sorted.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            recommended={route.id === plan.recommended_route_id}
            selected={route.id === selectedRouteId}
            onSelect={() => onSelect(route.id)}
          />
        ))}
      </div>
    </section>
  )
}

type RouteCardProps = {
  route: PlannedRoute
  recommended: boolean
  selected: boolean
  onSelect: () => void
}

function RouteCard({ route, recommended, selected, onSelect }: RouteCardProps) {
  const { summary } = route
  return (
    <button
      type="button"
      className={[
        'route-card',
        selected ? 'is-selected' : '',
        recommended ? 'is-recommended' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="route-card-top">
        <span className="route-card-id">Route {route.id}</span>
        {recommended ? <span className="route-badge">Recommended</span> : null}
      </div>
      <dl className="route-card-stats">
        <div>
          <dt>Distance</dt>
          <dd>{formatDistanceMi(summary.distance_mi)}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(summary.duration_s)}</dd>
        </div>
        <div>
          <dt>Arrival</dt>
          <dd>{formatEta(summary.arrival_time)}</dd>
        </div>
        <div>
          <dt>Avg risk</dt>
          <dd>{summary.avg_risk.toFixed(2)}</dd>
        </div>
      </dl>
      <div className="route-card-miles" aria-label="Miles by risk level">
        {RISK_LEVELS.map((level) => (
          <MilesChip
            key={level}
            level={level}
            miles={summary.miles_by_level[level] ?? 0}
          />
        ))}
      </div>
    </button>
  )
}

function MilesChip({ level, miles }: { level: RiskLevel; miles: number }) {
  if (miles <= 0) {
    return null
  }
  return (
    <span className="miles-chip" title={`${RISK_LABELS[level]} miles`}>
      <span className="risk-swatch" style={{ background: RISK_COLORS[level] }} />
      {formatMilesByLevel(miles)} mi {RISK_LABELS[level].toLowerCase()}
    </span>
  )
}
