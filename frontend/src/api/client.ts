export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text) as unknown
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, messageFromBody(body, response.status), body)
  }

  return body as T
}

function messageFromBody(body: unknown, status: number): string {
  if (typeof body === 'string' && body.trim()) {
    return body
  }
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>
    if (typeof record.detail === 'string') {
      return record.detail
    }
    const parts = Object.entries(record).flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.map((item) => `${key}: ${String(item)}`)
      }
      if (typeof value === 'string') {
        return [`${key}: ${value}`]
      }
      return [`${key}: ${JSON.stringify(value)}`]
    })
    if (parts.length > 0) {
      return parts.join(' · ')
    }
  }
  return `Request failed (HTTP ${status})`
}
