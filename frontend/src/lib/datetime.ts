/** Format a Date as `YYYY-MM-DDTHH:mm` for `<input type="datetime-local">`. */
export function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** Default departure: next whole hour in the browser's local zone. */
export function defaultDepartureLocal(): string {
  const date = new Date()
  date.setSeconds(0, 0)
  date.setMinutes(0)
  date.setHours(date.getHours() + 1)
  return toDatetimeLocalValue(date)
}

/**
 * Convert a datetime-local value into ISO-8601 with an explicit offset
 * (required by POST /api/trips/plan).
 */
export function localInputToIsoWithOffset(localValue: string): string {
  const date = new Date(localValue)
  if (Number.isNaN(date.getTime())) {
    throw new Error('Invalid departure time.')
  }

  const pad = (n: number) => String(n).padStart(2, '0')
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hour = pad(date.getHours())
  const minute = pad(date.getMinutes())
  const second = pad(date.getSeconds())

  const offsetMinutes = -date.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMinutes)
  const offsetHours = pad(Math.floor(abs / 60))
  const offsetMins = pad(abs % 60)

  return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${offsetHours}:${offsetMins}`
}
