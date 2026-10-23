import { apiFetch } from './client'
import type { Place } from './types'

export function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const q = query.trim()
  if (!q) {
    return Promise.resolve([])
  }
  const params = new URLSearchParams({ q })
  return apiFetch<Place[]>(`/api/geocode?${params.toString()}`, { signal })
}
