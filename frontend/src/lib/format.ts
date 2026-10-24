export function formatDistanceMi(miles: number): string {
  return `${miles.toLocaleString(undefined, { maximumFractionDigits: 1 })} mi`
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) {
    return `${minutes} min`
  }
  if (minutes === 0) {
    return `${hours} h`
  }
  return `${hours} h ${minutes} min`
}

export function formatEta(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatMilesByLevel(miles: number): string {
  if (miles <= 0) {
    return '0'
  }
  return miles.toLocaleString(undefined, { maximumFractionDigits: 1 })
}
