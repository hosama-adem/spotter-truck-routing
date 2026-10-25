import type { PlannedRoute } from '../api/types'

export type LngLatBoundsTuple = [[number, number], [number, number]]
export type LonLat = [number, number]

const EARTH_RADIUS_M = 6_371_000

function haversineM(a: LonLat, b: LonLat): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b[1] - a[1])
  const dLon = toRad(b[0] - a[0])
  const lat1 = toRad(a[1])
  const lat2 = toRad(b[1])
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

function cumulativeDistancesM(coords: LonLat[]): number[] {
  const distances = [0]
  for (let i = 1; i < coords.length; i += 1) {
    distances.push(distances[i - 1]! + haversineM(coords[i - 1]!, coords[i]!))
  }
  return distances
}

/**
 * Where the truck is after ``hourOffset`` hours of driving along the route,
 * capped at the destination when the trip duration is exceeded.
 */
export function positionAlongRoute(
  coordinates: LonLat[],
  durationS: number,
  hourOffset: number,
): LonLat | null {
  if (coordinates.length === 0) {
    return null
  }
  if (coordinates.length === 1 || durationS <= 0) {
    return coordinates[0]!
  }

  const elapsedS = Math.min(Math.max(hourOffset, 0) * 3600, durationS)
  const fraction = elapsedS / durationS
  const distances = cumulativeDistancesM(coordinates)
  const total = distances[distances.length - 1]!
  if (total <= 0) {
    return coordinates[0]!
  }

  const target = total * fraction
  for (let i = 1; i < distances.length; i += 1) {
    if (distances[i]! >= target) {
      const start = distances[i - 1]!
      const span = distances[i]! - start
      const t = span <= 0 ? 0 : (target - start) / span
      const [lon1, lat1] = coordinates[i - 1]!
      const [lon2, lat2] = coordinates[i]!
      return [lon1 + (lon2 - lon1) * t, lat1 + (lat2 - lat1) * t]
    }
  }
  return coordinates[coordinates.length - 1]!
}

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
