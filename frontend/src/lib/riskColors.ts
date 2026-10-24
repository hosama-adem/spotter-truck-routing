import type { RiskLevel } from '../api/types'

export const RISK_LEVELS: RiskLevel[] = [
  'LOW',
  'MODERATE',
  'HIGH',
  'SEVERE',
  'NO_TRAVEL',
]

/** CSS / map colors for each risk level (PRD legend). */
export const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  SEVERE: '#ef4444',
  NO_TRAVEL: '#7f1d1d',
}

export const RISK_LABELS: Record<RiskLevel, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  SEVERE: 'Severe',
  NO_TRAVEL: 'No travel',
}

export function riskRgba(level: RiskLevel, alpha = 255): [number, number, number, number] {
  const hex = RISK_COLORS[level].slice(1)
  const n = Number.parseInt(hex, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, alpha]
}
