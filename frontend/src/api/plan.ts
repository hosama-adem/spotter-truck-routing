import { apiFetch } from './client'
import type { PlanRequest, PlanResponse } from './types'

export function planTrip(
  payload: PlanRequest,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return apiFetch<PlanResponse>('/api/trips/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  })
}
