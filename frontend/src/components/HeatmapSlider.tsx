type HeatmapSliderProps = {
  hour: number
  maxHour: number
  startTime: string | null
  disabled?: boolean
  onChange: (hour: number) => void
}

function formatHourLabel(startTime: string | null, hour: number): string {
  if (!startTime) {
    return `+${hour}h`
  }
  const date = new Date(startTime)
  if (Number.isNaN(date.getTime())) {
    return `+${hour}h`
  }
  date.setTime(date.getTime() + hour * 3_600_000)
  const clock = date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `+${hour}h · ${clock}`
}

export function HeatmapSlider({
  hour,
  maxHour,
  startTime,
  disabled = false,
  onChange,
}: HeatmapSliderProps) {
  return (
    <div className="heatmap-slider">
      <div className="heatmap-slider-top">
        <span className="heatmap-slider-title">Weather risk over time</span>
        <span className="heatmap-slider-value">{formatHourLabel(startTime, hour)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={maxHour}
        step={1}
        value={hour}
        disabled={disabled}
        aria-label="Hours after departure"
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="heatmap-slider-ends">
        <span>Departure</span>
        <span>+{maxHour}h</span>
      </div>
    </div>
  )
}
