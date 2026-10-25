import type { HeatmapResponse } from '../api/types'

export type HeatmapPoint = {
  position: [number, number]
  weight: number
}

/** Precompute all 49 frames once; slider only indexes into this array. */
export function buildHeatmapFrames(heatmap: HeatmapResponse): HeatmapPoint[][] {
  return heatmap.risk.map((row) =>
    heatmap.points.map((position, index) => ({
      position,
      weight: row[index] ?? 0,
    })),
  )
}
