/**
 * MapaFocosReais — mapa interativo com focos REAIS do NASA FIRMS.
 * Usa react-map-gl + MapLibre GL.
 * Ao clicar num foco, abre o painel de explicação do agente.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import Map, {
  Layer,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type MapRef,
} from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { clsx } from 'clsx'
import type { FocoReal } from '../services/api'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const CEARA_CENTER = { longitude: -39.3, latitude: -5.1, zoom: 6.8 }

const SEV_COR: Record<string, string> = {
  baixa:   '#22c55e',
  media:   '#eab308',
  alta:    '#f97316',
  critica: '#ef4444',
}

const SEV_TAMANHO: Record<string, number> = {
  baixa: 8, media: 11, alta: 14, critica: 18,
}

interface Props {
  focos: FocoReal[]
  focoSelecionado: FocoReal | null
  onSelecionarFoco: (foco: FocoReal) => void
  mostrarHeatmap: boolean
  mostrarClusters: boolean
}

export default function MapaFocosReais({
  focos,
  focoSelecionado,
  onSelecionarFoco,
  mostrarHeatmap,
  mostrarClusters,
}: Props) {
  const mapRef = useRef<MapRef>(null)
  const [popupHover, setPopupHover] = useState<FocoReal | null>(null)

  // Centraliza no foco selecionado
  useEffect(() => {
    if (!focoSelecionado || !mapRef.current) return
    mapRef.current.flyTo({
      center: [focoSelecionado.lon, focoSelecionado.lat],
      zoom: 10,
      duration: 800,
    })
  }, [focoSelecionado])

  // GeoJSON para heatmap e clusters
  const focosGeoJSON = {
    type: 'FeatureCollection' as const,
    features: focos.map(f => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [f.lon, f.lat] },
      properties: {
        id: f.id,
        frp: f.frp ?? 1,
        severidade: f.severidade,
        municipio: f.municipio ?? '',
        sensor: f.sensor,
        data_hora: f.data_hora,
        confianca: f.confianca,
      },
    })),
  }

  const handleMarkerClick = useCallback(
    (e: React.MouseEvent, foco: FocoReal) => {
      e.stopPropagation()
      setPopupHover(null)
      onSelecionarFoco(foco)
    },
    [onSelecionarFoco]
  )

  // Focos críticos e altos renderizados como marcadores individuais (mais visíveis)
  const focosDestaque = focos.filter(f => f.severidade === 'critica' || f.severidade === 'alta')
  const focosNormais = focos.filter(f => f.severidade === 'media' || f.severidade === 'baixa')

  return (
    <div className="relative w-full h-full" role="region" aria-label="Real wildfire hotspot map">
      <Map
        ref={mapRef}
        initialViewState={CEARA_CENTER}
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
        interactiveLayerIds={mostrarClusters ? ['clusters', 'unclustered-point'] : []}
      >
        <NavigationControl position="top-right" />

        {/* ── Heatmap ── */}
        {mostrarHeatmap && (
          <Source id="heatmap-src" type="geojson" data={focosGeoJSON}>
            <Layer
              id="heatmap-layer"
              type="heatmap"
              paint={{
                'heatmap-weight': [
                  'interpolate', ['linear'], ['get', 'frp'],
                  0, 0, 5, 0.3, 20, 0.7, 50, 1,
                ],
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 5, 1, 10, 2],
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0,   'rgba(0,0,0,0)',
                  0.1, 'rgba(34,197,94,0.6)',
                  0.3, 'rgba(234,179,8,0.7)',
                  0.6, 'rgba(249,115,22,0.8)',
                  1,   'rgba(239,68,68,0.9)',
                ],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 5, 15, 10, 30],
                'heatmap-opacity': 0.75,
              }}
            />
          </Source>
        )}

        {/* ── Clusters (focos normais agrupados) ── */}
        {mostrarClusters && (
          <Source
            id="clusters-src"
            type="geojson"
            data={{
              type: 'FeatureCollection',
              features: focosNormais.map(f => ({
                type: 'Feature' as const,
                geometry: { type: 'Point' as const, coordinates: [f.lon, f.lat] },
                properties: { id: f.id, frp: f.frp ?? 1 },
              })),
            }}
            cluster
            clusterMaxZoom={9}
            clusterRadius={40}
          >
            <Layer
              id="clusters"
              type="circle"
              filter={['has', 'point_count']}
              paint={{
                'circle-color': ['step', ['get', 'point_count'], '#eab308', 5, '#f97316', 10, '#ef4444'],
                'circle-radius': ['step', ['get', 'point_count'], 14, 5, 18, 10, 22],
                'circle-opacity': 0.85,
                'circle-stroke-width': 2,
                'circle-stroke-color': '#fff',
              }}
            />
            <Layer
              id="cluster-count"
              type="symbol"
              filter={['has', 'point_count']}
              layout={{
                'text-field': '{point_count_abbreviated}',
                'text-size': 11,
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
              }}
              paint={{ 'text-color': '#fff' }}
            />
            <Layer
              id="unclustered-point"
              type="circle"
              filter={['!', ['has', 'point_count']]}
              paint={{
                'circle-color': '#eab308',
                'circle-radius': 5,
                'circle-opacity': 0.8,
                'circle-stroke-width': 1,
                'circle-stroke-color': '#fff',
              }}
            />
          </Source>
        )}

        {/* ── Marcadores individuais para focos críticos/altos ── */}
        {focosDestaque.map(foco => {
          const selecionado = focoSelecionado?.id === foco.id
          const tamanho = SEV_TAMANHO[foco.severidade]
          const cor = SEV_COR[foco.severidade]

          return (
            <Marker
              key={foco.id}
              longitude={foco.lon}
              latitude={foco.lat}
              anchor="center"
            >
              <button
                onClick={e => handleMarkerClick(e, foco)}
                onMouseEnter={() => setPopupHover(foco)}
                onMouseLeave={() => setPopupHover(null)}
                className="relative cursor-pointer transition-transform hover:scale-125 focus:outline-none"
                style={{ width: tamanho, height: tamanho }}
                aria-label={`${foco.severidade} hotspot in ${foco.municipio ?? 'Ceará'}`}
              >
                {/* Anel pulsante para críticos */}
                {foco.severidade === 'critica' && (
                  <span
                    className="absolute inset-0 rounded-full animate-ping opacity-60"
                    style={{ backgroundColor: cor }}
                  />
                )}
                {/* Círculo principal */}
                <span
                  className={clsx(
                    'absolute inset-0 rounded-full border-2',
                    selecionado ? 'border-white scale-125' : 'border-white/40'
                  )}
                  style={{ backgroundColor: cor }}
                />
                {/* Ícone de chama para críticos */}
                {foco.severidade === 'critica' && (
                  <span className="absolute inset-0 flex items-center justify-center text-slate-900 text-[8px] font-bold">
                    🔥
                  </span>
                )}
              </button>
            </Marker>
          )
        })}

        {/* ── Marcadores normais (quando clusters desativado) ── */}
        {!mostrarClusters && focosNormais.map(foco => {
          const selecionado = focoSelecionado?.id === foco.id
          return (
            <Marker
              key={foco.id}
              longitude={foco.lon}
              latitude={foco.lat}
              anchor="center"
            >
              <button
                onClick={e => handleMarkerClick(e, foco)}
                onMouseEnter={() => setPopupHover(foco)}
                onMouseLeave={() => setPopupHover(null)}
                className={clsx(
                  'w-2.5 h-2.5 rounded-full border cursor-pointer transition-transform hover:scale-150',
                  selecionado ? 'border-white scale-150' : 'border-white/30'
                )}
                style={{ backgroundColor: SEV_COR[foco.severidade] }}
                aria-label={`${foco.severidade} hotspot in ${foco.municipio ?? 'Ceará'}`}
              />
            </Marker>
          )
        })}

        {/* ── Popup hover ── */}
        {popupHover && (
          <Popup
            longitude={popupHover.lon}
            latitude={popupHover.lat}
            onClose={() => setPopupHover(null)}
            closeButton={false}
            anchor="bottom"
            offset={12}
          >
            <div className="text-gray-900 text-xs space-y-0.5 min-w-[140px] p-1">
              <p className="font-bold text-sm">{popupHover.municipio ?? 'Ceará'}</p>
              <p>
                <span className="text-slate-500">Sensor:</span>{' '}
                <strong>{popupHover.sensor}</strong>
              </p>
              {popupHover.frp != null && (
                <p>
                  <span className="text-slate-500">FRP:</span>{' '}
                  <strong>{popupHover.frp.toFixed(1)} MW</strong>
                </p>
              )}
              <p>
                <span className="text-slate-500">Confidence:</span>{' '}
                <strong>{popupHover.confianca.toFixed(0)}%</strong>
              </p>
              <p className="text-slate-500 pt-0.5">Click to view agent analysis</p>
            </div>
          </Popup>
        )}

        {/* ── Popup do foco selecionado ── */}
        {focoSelecionado && !popupHover && (
          <Popup
            longitude={focoSelecionado.lon}
            latitude={focoSelecionado.lat}
            onClose={() => {}}
            closeButton={false}
            anchor="top"
            offset={12}
          >
            <div className="text-gray-900 text-xs p-1">
              <p className="font-bold">📍 {focoSelecionado.municipio ?? 'Selected'}</p>
              <p className="text-slate-500">View analysis in panel →</p>
            </div>
          </Popup>
        )}
      </Map>

      {/* ── Legenda ── */}
      <div className="absolute bottom-4 left-4 bg-white/95 border border-slate-200 rounded-xl p-3 text-xs space-y-1.5 backdrop-blur-sm">
        <p className="font-semibold text-slate-600 mb-2">Severity (FRP)</p>
        {[
          { sev: 'critica', label: 'Critical (≥50 MW)', pulse: true },
          { sev: 'alta',    label: 'High (15–50 MW)',  pulse: false },
          { sev: 'media',   label: 'Medium (5–15 MW)',  pulse: false },
          { sev: 'baixa',   label: 'Low (<5 MW)',    pulse: false },
        ].map(({ sev, label, pulse }) => (
          <div key={sev} className="flex items-center gap-2">
            <div className="relative w-3 h-3 shrink-0">
              {pulse && (
                <span
                  className="absolute inset-0 rounded-full animate-ping opacity-50"
                  style={{ backgroundColor: SEV_COR[sev] }}
                />
              )}
              <span
                className="absolute inset-0 rounded-full"
                style={{ backgroundColor: SEV_COR[sev] }}
              />
            </div>
            <span className="text-slate-500">{label}</span>
          </div>
        ))}
        <div className="pt-1 border-t border-slate-200 text-slate-500">
          Source: NASA FIRMS (VIIRS/MODIS)
        </div>
      </div>
    </div>
  )
}
