import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import { useEffect, useMemo, useState } from 'react'
import {
  Map,
  Marker,
  NavigationControl,
  Popup,
  useControl,
  type MapRef,
} from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import type {
  Checkpoint,
  HeatmapResponse,
  PlanResponse,
  PlannedRoute,
} from '../api/types'
import {
  formatDistanceMi,
  formatDuration,
  formatEta,
} from '../lib/format'
import { boundsForRoutes, positionAlongRoute } from '../lib/geo'
import { buildHeatmapFrames } from '../lib/heatmapFrames'
import { RISK_COLORS, RISK_LABELS, riskRgba } from '../lib/riskColors'
import { HeatmapSlider } from './HeatmapSlider'
import { RiskLegend } from './RiskLegend'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const MAX_SLIDER_HOUR = 48

type TripMapProps = {
  plan: PlanResponse
  selectedRouteId: string
  onSelectRoute: (routeId: string) => void
  heatmap: HeatmapResponse | null
  heatmapLoading: boolean
  heatmapError: string | null
  hour: number
  onHourChange: (hour: number) => void
}

type CheckpointFeature = Checkpoint & {
  routeId: string
}

function DeckGLOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props))
  overlay.setProps(props)
  return null
}

export function TripMap({
  plan,
  selectedRouteId,
  onSelectRoute,
  heatmap,
  heatmapLoading,
  heatmapError,
  hour,
  onHourChange,
}: TripMapProps) {
  const [mapRef, setMapRef] = useState<MapRef | null>(null)
  const [popup, setPopup] = useState<CheckpointFeature | null>(null)

  const bounds = useMemo(() => boundsForRoutes(plan.routes), [plan.routes])
  const frames = useMemo(
    () => (heatmap ? buildHeatmapFrames(heatmap) : []),
    [heatmap],
  )
  const frameData = useMemo(() => frames[hour] ?? [], [frames, hour])

  const recommended = plan.routes.find((route) => route.id === plan.recommended_route_id)
  const truckPosition = useMemo(() => {
    if (!recommended) {
      return null
    }
    return positionAlongRoute(
      recommended.geometry.coordinates as [number, number][],
      recommended.summary.duration_s,
      hour,
    )
  }, [recommended, hour])

  useEffect(() => {
    if (!mapRef || !bounds) {
      return
    }
    mapRef.fitBounds(bounds, { padding: 56, duration: 800 })
  }, [mapRef, bounds, plan.recommended_route_id])

  const layers = useMemo(() => {
    const heatmapLayer =
      frameData.length > 0
        ? new HeatmapLayer<{ position: [number, number]; weight: number }>({
            id: 'corridor-heatmap',
            data: frameData,
            getPosition: (d) => d.position,
            getWeight: (d) => d.weight,
            radiusPixels: 42,
            intensity: 1.15,
            threshold: 0.08,
            colorRange: [
              [34, 197, 94, 0],
              [34, 197, 94, 160],
              [234, 179, 8, 180],
              [249, 115, 22, 200],
              [239, 68, 68, 220],
              [127, 29, 29, 240],
            ],
          })
        : null

    const ordered = orderForDraw(plan.routes, selectedRouteId, plan.recommended_route_id)
    const pathLayers = ordered.map(
      (route) =>
        new PathLayer<{ path: [number, number][]; routeId: string }>({
          id: `route-path-${route.id}`,
          data: [
            {
              path: route.geometry.coordinates as [number, number][],
              routeId: route.id,
            },
          ],
          getPath: (d) => d.path,
          getColor: () => routeLineColor(route.id, selectedRouteId, plan.recommended_route_id),
          getWidth: () =>
            route.id === selectedRouteId ? 7 : route.id === plan.recommended_route_id ? 5 : 3,
          widthUnits: 'pixels',
          widthMinPixels: 2,
          pickable: true,
          capRounded: true,
          jointRounded: true,
        }),
    )

    const checkpoints: CheckpointFeature[] = plan.routes.flatMap((route) =>
      route.checkpoints.map((point) => ({ ...point, routeId: route.id })),
    )

    const checkpointLayer = new ScatterplotLayer<CheckpointFeature>({
      id: 'checkpoints',
      data: checkpoints,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => riskRgba(d.risk.level, d.routeId === selectedRouteId ? 240 : 160),
      getLineColor: [255, 255, 255, 220],
      getRadius: (d) => (d.routeId === selectedRouteId ? 7 : 5),
      radiusUnits: 'pixels',
      radiusMinPixels: 4,
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
    })

    return [heatmapLayer, ...pathLayers, checkpointLayer].filter(Boolean)
  }, [plan, selectedRouteId, frameData])

  return (
    <div className="trip-map-panel">
      <div className="trip-map-shell">
        <Map
          ref={setMapRef}
          mapStyle={MAP_STYLE}
          initialViewState={{ longitude: -98.5, latitude: 39.8, zoom: 3.4 }}
          style={{ width: '100%', height: '100%' }}
        >
          <NavigationControl position="top-right" />
          <DeckGLOverlay
            layers={layers}
            interleaved
            getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
            onClick={(info) => {
              if (!info.object) {
                setPopup(null)
                return
              }
              if ('risk' in info.object && 'routeId' in info.object) {
                const point = info.object as CheckpointFeature
                onSelectRoute(point.routeId)
                setPopup(point)
                return
              }
              if ('routeId' in info.object) {
                onSelectRoute((info.object as { routeId: string }).routeId)
                setPopup(null)
              }
            }}
          />
          {truckPosition ? (
            <Marker longitude={truckPosition[0]} latitude={truckPosition[1]} anchor="center">
              <div className="truck-marker" title="Truck position at selected hour" aria-hidden>
                <span className="truck-marker-dot" />
              </div>
            </Marker>
          ) : null}
          {popup && popup.routeId === selectedRouteId ? (
            <Popup
              longitude={popup.lon}
              latitude={popup.lat}
              anchor="bottom"
              offset={14}
              closeOnClick={false}
              onClose={() => setPopup(null)}
              maxWidth="280px"
            >
              <CheckpointPopupBody point={popup} />
            </Popup>
          ) : null}
        </Map>
        <RiskLegend />
        <p className="trip-map-hint">
          Selected Route {selectedRouteId}
          {' · '}
          {formatDistanceMi(
            plan.routes.find((r) => r.id === selectedRouteId)?.summary.distance_mi ?? 0,
          )}
          {' · '}
          {formatDuration(
            plan.routes.find((r) => r.id === selectedRouteId)?.summary.duration_s ?? 0,
          )}
        </p>
      </div>

      <HeatmapSlider
        hour={hour}
        maxHour={MAX_SLIDER_HOUR}
        startTime={heatmap?.start_time ?? null}
        disabled={!heatmap || heatmapLoading}
        onChange={onHourChange}
      />

      {heatmapLoading ? (
        <p className="heatmap-status">Loading corridor heatmap…</p>
      ) : null}
      {heatmapError ? (
        <p className="heatmap-status heatmap-status-error" role="alert">
          {heatmapError}
        </p>
      ) : null}
      {heatmap && !heatmapLoading ? (
        <p className="heatmap-status heatmap-status-ok">
          {heatmap.points.length} corridor points · {heatmap.hours} frames loaded — scrubbing is
          local only
        </p>
      ) : null}
    </div>
  )
}

function CheckpointPopupBody({ point }: { point: CheckpointFeature }) {
  const drivers =
    point.risk.drivers.length > 0 ? point.risk.drivers.join(', ') : 'within thresholds'
  return (
    <div className="checkpoint-popup">
      <p className="checkpoint-popup-title">
        Mile {point.mile.toFixed(0)}
        <span
          className="risk-pill"
          style={{ background: RISK_COLORS[point.risk.level] }}
        >
          {RISK_LABELS[point.risk.level]}
        </span>
      </p>
      <dl>
        <div>
          <dt>ETA</dt>
          <dd>{formatEta(point.eta)}</dd>
        </div>
        <div>
          <dt>Wind</dt>
          <dd>
            {point.weather.wind_mph.toFixed(0)} mph
            <span className="muted"> (gust {point.weather.gust_mph.toFixed(0)})</span>
          </dd>
        </div>
        <div>
          <dt>Rain</dt>
          <dd>{point.weather.rain_in_hr.toFixed(2)} in/hr</dd>
        </div>
        <div>
          <dt>Snow</dt>
          <dd>{point.weather.snow_in_hr.toFixed(2)} in/hr</dd>
        </div>
        <div>
          <dt>Why</dt>
          <dd>{drivers}</dd>
        </div>
      </dl>
    </div>
  )
}

function orderForDraw(
  routes: PlannedRoute[],
  selectedRouteId: string,
  recommendedRouteId: string,
): PlannedRoute[] {
  return [...routes].sort((a, b) => {
    const score = (route: PlannedRoute) => {
      if (route.id === selectedRouteId) {
        return 2
      }
      if (route.id === recommendedRouteId) {
        return 1
      }
      return 0
    }
    return score(a) - score(b)
  })
}

function routeLineColor(
  routeId: string,
  selectedRouteId: string,
  recommendedRouteId: string,
): [number, number, number, number] {
  if (routeId === selectedRouteId) {
    return routeId === recommendedRouteId ? [15, 110, 86, 255] : [29, 78, 137, 255]
  }
  if (routeId === recommendedRouteId) {
    return [15, 110, 86, 170]
  }
  return [120, 136, 152, 120]
}
