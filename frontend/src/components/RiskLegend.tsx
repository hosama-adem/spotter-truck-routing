import { RISK_COLORS, RISK_LABELS, RISK_LEVELS } from '../lib/riskColors'

export function RiskLegend() {
  return (
    <div className="risk-legend" aria-label="Risk level legend">
      <p className="risk-legend-title">Risk</p>
      <ul>
        {RISK_LEVELS.map((level) => (
          <li key={level}>
            <span
              className="risk-swatch"
              style={{ background: RISK_COLORS[level] }}
              aria-hidden
            />
            <span>{RISK_LABELS[level]}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
