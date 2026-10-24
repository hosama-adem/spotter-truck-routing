import type { PlannedRoute } from '../api/types'

export type LngLatBoundsTuple = [[number, number], [number, number]]

/** Bounding box covering all route geometries, padded slightly. */
export function boundsForRoutes(routes: PlannedRoute[]): LngLatBoundsTuple | null {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity
  let found = false

  for (const route of routes) {
    for (const [lon, lat] of route.geometry.coordinates) {
      found = true
      minLon = Math.min(minLon, lon)
      minLat = Math.min(minLat, lat)
      maxLon = Math.max(maxLon, lon)
      maxLat = Math.max(maxLat, lat)
    }
  }

  if (!found) {
    return null
  }

  const padLon = Math.max((maxLon - minLon) * 0.08, 0.15)
  const padLat = Math.max((maxLat - minLat) * 0.08, 0.15)
  return [
    [minLon - padLon, minLat - padLat],
    [maxLon + padLon, maxLat + padLat],
  ]
}
