import { useState, type FormEvent } from 'react'

import { ApiError } from '../api/client'
import { planTrip } from '../api/plan'
import type { Place, PlanResponse, TripPlanContext } from '../api/types'
import {
  defaultDepartureLocal,
  localInputToIsoWithOffset,
} from '../lib/datetime'
import { PlaceAutocomplete } from './PlaceAutocomplete'

const INTERVALS = [10, 25, 50] as const
const MIN_LOAD_LB = 1
const MAX_LOAD_LB = 80_000

export type TripFormValues = {
  origin: Place | null
  destination: Place | null
  departureLocal: string
  loadWeightLb: string
  checkpointIntervalMi: (typeof INTERVALS)[number]
}

type FieldErrors = Partial<
  Record<
    'origin' | 'destination' | 'departureLocal' | 'loadWeightLb' | 'checkpointIntervalMi',
    string
  >
>

type TripFormProps = {
  onPlanned: (result: PlanResponse, context: TripPlanContext) => void
}

function emptyValues(): TripFormValues {
  return {
    origin: null,
    destination: null,
    departureLocal: defaultDepartureLocal(),
    loadWeightLb: '42000',
    checkpointIntervalMi: 25,
  }
}

function validate(values: TripFormValues, originQuery: string, destQuery: string): FieldErrors {
  const errors: FieldErrors = {}

  if (!values.origin) {
    errors.origin = originQuery.trim()
      ? 'Pick a place from the suggestions.'
      : 'Origin is required.'
  }
  if (!values.destination) {
    errors.destination = destQuery.trim()
      ? 'Pick a place from the suggestions.'
      : 'Destination is required.'
  }
  if (
    values.origin &&
    values.destination &&
    values.origin.lat === values.destination.lat &&
    values.origin.lon === values.destination.lon
  ) {
    errors.destination = 'Origin and destination must be different.'
  }

  if (!values.departureLocal.trim()) {
    errors.departureLocal = 'Departure time is required.'
  } else {
    try {
      localInputToIsoWithOffset(values.departureLocal)
    } catch {
      errors.departureLocal = 'Enter a valid departure date and time.'
    }
  }

  const load = Number(values.loadWeightLb)
  if (!Number.isFinite(load) || values.loadWeightLb.trim() === '') {
    errors.loadWeightLb = 'Load weight is required.'
  } else if (load < MIN_LOAD_LB || load > MAX_LOAD_LB) {
    errors.loadWeightLb = `Load must be between ${MIN_LOAD_LB.toLocaleString()} and ${MAX_LOAD_LB.toLocaleString()} lb.`
  }

  if (!INTERVALS.includes(values.checkpointIntervalMi)) {
    errors.checkpointIntervalMi = 'Interval must be 10, 25, or 50 miles.'
  }

  return errors
}

export function TripForm({ onPlanned }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(emptyValues)
  const [originQuery, setOriginQuery] = useState('')
  const [destQuery, setDestQuery] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate(values, originQuery, destQuery)
    setErrors(nextErrors)
    setFormError(null)
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    const origin = values.origin!
    const destination = values.destination!
    setLoading(true)
    try {
      const departure_time = localInputToIsoWithOffset(values.departureLocal)
      const load_weight_lb = Number(values.loadWeightLb)
      const result = await planTrip({
        origin,
        destination,
        departure_time,
        load_weight_lb,
        checkpoint_interval_mi: values.checkpointIntervalMi,
      })
      onPlanned(result, { departure_time, load_weight_lb })
    } catch (err: unknown) {
      setFormError(
        err instanceof ApiError
          ? err.message
          : 'Could not plan this trip. Check the API and try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="trip-form" onSubmit={onSubmit} noValidate>
      <header className="trip-form-header">
        <h2>Plan a trip</h2>
        <p>Set origin, destination, departure, and load — we&apos;ll rank three truck corridors by weather risk.</p>
      </header>

      <div className="trip-form-grid">
        <PlaceAutocomplete
          label="Origin"
          value={values.origin}
          query={originQuery}
          disabled={loading}
          error={errors.origin}
          onQueryChange={(query) => {
            setOriginQuery(query)
            setValues((prev) => ({ ...prev, origin: null }))
            setErrors((prev) => ({ ...prev, origin: undefined }))
          }}
          onSelect={(place) => {
            setValues((prev) => ({ ...prev, origin: place }))
            setErrors((prev) => ({ ...prev, origin: undefined }))
          }}
        />

        <PlaceAutocomplete
          label="Destination"
          value={values.destination}
          query={destQuery}
          disabled={loading}
          error={errors.destination}
          onQueryChange={(query) => {
            setDestQuery(query)
            setValues((prev) => ({ ...prev, destination: null }))
            setErrors((prev) => ({ ...prev, destination: undefined }))
          }}
          onSelect={(place) => {
            setValues((prev) => ({ ...prev, destination: place }))
            setErrors((prev) => ({ ...prev, destination: undefined }))
          }}
        />

        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={values.departureLocal}
            disabled={loading}
            onChange={(event) => {
              setValues((prev) => ({ ...prev, departureLocal: event.target.value }))
              setErrors((prev) => ({ ...prev, departureLocal: undefined }))
            }}
          />
          <p className="field-hint">Sent with your local timezone offset</p>
          {errors.departureLocal ? (
            <p className="field-error">{errors.departureLocal}</p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={MIN_LOAD_LB}
            max={MAX_LOAD_LB}
            step={100}
            value={values.loadWeightLb}
            disabled={loading}
            onChange={(event) => {
              setValues((prev) => ({ ...prev, loadWeightLb: event.target.value }))
              setErrors((prev) => ({ ...prev, loadWeightLb: undefined }))
            }}
          />
          {errors.loadWeightLb ? (
            <p className="field-error">{errors.loadWeightLb}</p>
          ) : null}
        </div>

        <fieldset className="field field-span">
          <legend>Checkpoint interval</legend>
          <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
            {INTERVALS.map((miles) => {
              const selected = values.checkpointIntervalMi === miles
              return (
                <label key={miles} className={selected ? 'is-selected' : undefined}>
                  <input
                    type="radio"
                    name="checkpoint_interval_mi"
                    value={miles}
                    checked={selected}
                    disabled={loading}
                    onChange={() => {
                      setValues((prev) => ({
                        ...prev,
                        checkpointIntervalMi: miles,
                      }))
                      setErrors((prev) => ({
                        ...prev,
                        checkpointIntervalMi: undefined,
                      }))
                    }}
                  />
                  {miles} mi
                </label>
              )
            })}
          </div>
          {errors.checkpointIntervalMi ? (
            <p className="field-error">{errors.checkpointIntervalMi}</p>
          ) : null}
        </fieldset>
      </div>

      {formError ? (
        <p className="form-banner form-banner-error" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="trip-form-actions">
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Planning routes…' : 'Plan trip'}
        </button>
      </div>
    </form>
  )
}
