import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import { useEffect, useMemo, useState } from 'react'
import {
  Map,
  NavigationControl,
  Popup,
  useControl,
  type MapRef,
} from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import type { Checkpoint, PlanResponse, PlannedRoute } from '../api/types'
import {
  formatDistanceMi,
  formatDuration,
  formatEta,
} from '../lib/format'
import { boundsForRoutes } from '../lib/geo'
import { RISK_COLORS, RISK_LABELS, riskRgba } from '../lib/riskColors'
import { RiskLegend } from './RiskLegend'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

type TripMapProps = {
  plan: PlanResponse
  selectedRouteId: string
  onSelectRoute: (routeId: string) => void
}

type CheckpointFeature = Checkpoint & {
  routeId: string
}

function DeckGLOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props))
  overlay.setProps(props)
  return null
}

export function TripMap({ plan, selectedRouteId, onSelectRoute }: TripMapProps) {
  const [mapRef, setMapRef] = useState<MapRef | null>(null)
  const [popup, setPopup] = useState<CheckpointFeature | null>(null)

  const bounds = useMemo(() => boundsForRoutes(plan.routes), [plan.routes])

  useEffect(() => {
    if (!mapRef || !bounds) {
      return
    }
    mapRef.fitBounds(bounds, { padding: 56, duration: 800 })
  }, [mapRef, bounds, plan.recommended_route_id])

  const layers = useMemo(() => {
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

    return [...pathLayers, checkpointLayer]
  }, [plan, selectedRouteId])

  return (
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
