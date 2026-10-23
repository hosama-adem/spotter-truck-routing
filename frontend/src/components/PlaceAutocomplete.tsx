import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'

import { ApiError } from '../api/client'
import { searchPlaces } from '../api/geocode'
import type { Place } from '../api/types'

const DEBOUNCE_MS = 300
const MIN_QUERY_LEN = 2

type PlaceAutocompleteProps = {
  id?: string
  label: string
  value: Place | null
  query: string
  onQueryChange: (query: string) => void
  onSelect: (place: Place) => void
  error?: string
  disabled?: boolean
}

export function PlaceAutocomplete({
  id: idProp,
  label,
  value,
  query,
  onQueryChange,
  onSelect,
  error,
  disabled = false,
}: PlaceAutocompleteProps) {
  const generatedId = useId()
  const inputId = idProp ?? generatedId
  const listId = `${inputId}-list`
  const rootRef = useRef<HTMLDivElement>(null)

  const [suggestions, setSuggestions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [highlight, setHighlight] = useState(-1)

  const trimmed = query.trim()
  const resolved = Boolean(value && trimmed === value.label)
  const canSearch = !resolved && trimmed.length >= MIN_QUERY_LEN

  useEffect(() => {
    if (!canSearch) {
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      setSearchError(null)
      searchPlaces(trimmed, controller.signal)
        .then((results) => {
          setSuggestions(results)
          setOpen(true)
          setHighlight(-1)
        })
        .catch((err: unknown) => {
          if (err instanceof Error && err.name === 'AbortError') {
            return
          }
          setSuggestions([])
          setOpen(false)
          setSearchError(
            err instanceof ApiError
              ? err.message
              : 'Could not search places. Try again.',
          )
        })
        .finally(() => setLoading(false))
    }, DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [canSearch, trimmed])

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  function choose(place: Place) {
    onSelect(place)
    onQueryChange(place.label)
    setSuggestions([])
    setOpen(false)
    setHighlight(-1)
    setSearchError(null)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) {
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((prev) => (prev + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1))
    } else if (event.key === 'Enter' && highlight >= 0) {
      event.preventDefault()
      choose(suggestions[highlight]!)
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = canSearch && open && suggestions.length > 0
  const resolvedHint =
    value && resolved ? `${value.lat.toFixed(4)}, ${value.lon.toFixed(4)}` : null

  return (
    <div className="field" ref={rootRef}>
      <label htmlFor={inputId}>{label}</label>
      <div className="autocomplete">
        <input
          id={inputId}
          type="text"
          autoComplete="off"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            highlight >= 0 ? `${listId}-option-${highlight}` : undefined
          }
          value={query}
          disabled={disabled}
          placeholder="City, state, or address"
          onChange={(event) => {
            onQueryChange(event.target.value)
          }}
          onFocus={() => {
            if (canSearch && suggestions.length > 0) {
              setOpen(true)
            }
          }}
          onKeyDown={onKeyDown}
        />
        {loading && canSearch ? (
          <span className="autocomplete-status">Searching…</span>
        ) : null}
        {showList ? (
          <ul id={listId} className="suggestions" role="listbox">
            {suggestions.map((place, index) => (
              <li
                key={`${place.label}-${place.lat}-${place.lon}-${index}`}
                role="presentation"
              >
                <button
                  type="button"
                  id={`${listId}-option-${index}`}
                  role="option"
                  aria-selected={index === highlight}
                  className={index === highlight ? 'is-active' : undefined}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => choose(place)}
                >
                  {place.label}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {resolvedHint ? <p className="field-hint">{resolvedHint}</p> : null}
      {searchError && canSearch ? (
        <p className="field-error">{searchError}</p>
      ) : null}
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  )
}
