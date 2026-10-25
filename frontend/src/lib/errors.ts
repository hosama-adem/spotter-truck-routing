import { ApiError } from '../api/client'

/** Turn API / network failures into short, human copy. */
export function humanizeApiError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      return 'Service isn’t configured yet (missing API key on the server).'
    }
    if (err.status === 502) {
      return 'Upstream routing or weather failed. Wait a moment and retry.'
    }
    if (err.status === 400 && err.message.trim()) {
      return err.message
    }
    if (err.message.trim()) {
      return err.message
    }
  }
  if (err instanceof TypeError) {
    return 'Could not reach the API. Check that the backend is running, then retry.'
  }
  if (err instanceof Error && err.message.trim()) {
    return err.message
  }
  return fallback
}
