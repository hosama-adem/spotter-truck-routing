import { apiFetch } from './client'
import type { HeatmapRequest, HeatmapResponse } from './types'

export function fetchHeatmap(
  payload: HeatmapRequest,
  signal?: AbortSignal,
): Promise<HeatmapResponse> {
  return apiFetch<HeatmapResponse>('/api/weather/heatmap', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  })
}
