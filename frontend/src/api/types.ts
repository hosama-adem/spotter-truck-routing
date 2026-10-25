/** Shared API shapes aligned with PRD §7. */

export type Place = {
  label: string
  lat: number
  lon: number
}

export type PlanRequest = {
  origin: Place
  destination: Place
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_mi: 10 | 25 | 50
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL'

export type Checkpoint = {
  mile: number
  lat: number
  lon: number
  eta: string
  weather: {
    wind_mph: number
    gust_mph: number
    rain_in_hr: number
    snow_in_hr: number
  }
  risk: {
    level: RiskLevel
    score: number
    drivers: string[]
  }
}

export type RouteSummary = {
  distance_mi: number
  duration_s: number
  arrival_time: string
  miles_by_level: Record<RiskLevel, number>
  avg_risk: number
  max_level: RiskLevel
}

export type PlannedRoute = {
  id: string
  rank: number
  geometry: {
    type: 'LineString'
    coordinates: [number, number][]
  }
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export type PlanResponse = {
  recommended_route_id: string
  recommendation_reason: string
  routes: PlannedRoute[]
}

/** Inputs needed again for POST /api/weather/heatmap after a plan. */
export type TripPlanContext = {
  departure_time: string
  load_weight_lb: number
}

export type HeatmapRequest = {
  departure_time: string
  load_weight_lb: number
  geometry: {
    type: 'LineString'
    coordinates: [number, number][]
  }
}

/** Compact corridor × 49 hourly risk frames (PRD §7). */
export type HeatmapResponse = {
  start_time: string
  hours: number
  points: [number, number][]
  risk: number[][]
}
