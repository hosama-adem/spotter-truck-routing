import { useEffect, useState } from 'react'

type HealthState =
  | { kind: 'loading' }
  | { kind: 'ok'; body: string }
  | { kind: 'error'; message: string }

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(
  /\/$/,
  '',
)
const healthUrl = `${apiBaseUrl}/api/health`

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

function App() {
  const [health, setHealth] = useState<HealthState>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()

    fetch(healthUrl, { signal: controller.signal })
      .then(async (response) => {
        const body = await response.text()
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        setHealth({ kind: 'ok', body })
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return
        }
        const message = error instanceof Error ? error.message : 'Request failed'
        setHealth({ kind: 'error', message })
      })

    return () => controller.abort()
  }, [])

  return (
    <main>
      <h1>Weather-Aware Truck Routing</h1>
      <p>Skeleton check against the API.</p>
      <p>
        <code>{healthUrl}</code>
      </p>
      {health.kind === 'loading' ? <p>Checking backend…</p> : null}
      {health.kind === 'ok' ? <p>Backend responded: {health.body}</p> : null}
      {health.kind === 'error' ? (
        <p>Could not reach the backend ({health.message}). Start it, then refresh.</p>
      ) : null}
    </main>
  )
}

export default App
