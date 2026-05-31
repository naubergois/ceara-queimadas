/**
 * MapaQueimadas — mapa interativo com focos, GOES-16 e camadas territoriais.
 * Usa react-map-gl + MapLibre GL.
 */

import { useCallback, useState } from 'react'
import Map, { Layer, Marker, NavigationControl, Popup, Source } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Foco, LeituraGOES16 } from '../services/api'
import { useQueimadasStore } from '../store/useQueimadasStore'
import { clsx } from 'clsx'

// Mapa base gratuito (OpenStreetMap via MapTiler ou Carto)
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// Centro do Ceará
const CEARA_CENTER = { longitude: -39.3, latitude: -5.1, zoom: 6.5 }

const severidadeCor: Record<string, string> = {
  baixa: '#22c55e',
  media: '#eab308',
  alta: '#f97316',
  critica: '#ef4444',
}

interface Props {
  focos: Foco[]
  leituraGOES16: LeituraGOES16[]
}

export default function MapaQueimadas({ focos, leituraGOES16 }: Props) {
  const camadas = useQueimadasStore((s) => s.camadas)
  const [popupFoco, setPopupFoco] = useState<Foco | null>(null)
  const [popupGOES, setPopupGOES] = useState<LeituraGOES16 | null>(null)

  const camadasAtivas = new Set(camadas.filter((c) => c.ativo).map((c) => c.id))

  // GeoJSON para heatmap de focos
  const focosGeoJSON = {
    type: 'FeatureCollection' as const,
    features: focos.map((f) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [f.lon, f.lat] },
      properties: { frp: f.frp ?? 1, severidade: f.severidade ?? 'baixa' },
    })),
  }

  const handleFocoClick = useCallback((foco: Foco) => {
    setPopupGOES(null)
    setPopupFoco(foco)
  }, [])

  const handleGOESClick = useCallback((l: LeituraGOES16) => {
    setPopupFoco(null)
    setPopupGOES(l)
  }, [])

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden" role="region" aria-label="Mapa de queimadas do Ceará">
      <Map
        initialViewState={CEARA_CENTER}
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
      >
        <NavigationControl position="top-right" />

        {/* Heatmap de concentração */}
        {camadasAtivas.has('heatmap') && (
          <Source id="heatmap-source" type="geojson" data={focosGeoJSON}>
            <Layer
              id="heatmap-layer"
              type="heatmap"
              paint={{
                'heatmap-weight': ['interpolate', ['linear'], ['get', 'frp'], 0, 0, 100, 1],
                'heatmap-intensity': 1.5,
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(0,0,0,0)',
                  0.2, '#22c55e',
                  0.5, '#eab308',
                  0.8, '#f97316',
                  1, '#ef4444',
                ],
                'heatmap-radius': 20,
                'heatmap-opacity': 0.7,
              }}
            />
          </Source>
        )}

        {/* Marcadores INPE */}
        {camadasAtivas.has('focos_inpe') &&
          focos
            .filter((f) => f.fonte === 'INPE')
            .map((f) => (
              <Marker
                key={f.id}
                longitude={f.lon}
                latitude={f.lat}
                onClick={() => handleFocoClick(f)}
                anchor="center"
              >
                <button
                  className="w-3 h-3 rounded-full border border-white/30 cursor-pointer hover:scale-150 transition-transform"
                  style={{ backgroundColor: severidadeCor[f.severidade ?? 'baixa'] }}
                  aria-label={`Foco INPE em ${f.municipio ?? 'localização desconhecida'}`}
                />
              </Marker>
            ))}

        {/* Marcadores NASA FIRMS */}
        {camadasAtivas.has('focos_firms') &&
          focos
            .filter((f) => f.fonte === 'NASA_FIRMS')
            .map((f) => (
              <Marker
                key={f.id}
                longitude={f.lon}
                latitude={f.lat}
                onClick={() => handleFocoClick(f)}
                anchor="center"
              >
                <button
                  className="w-3 h-3 rounded-full border-2 border-blue-400 cursor-pointer hover:scale-150 transition-transform"
                  style={{ backgroundColor: severidadeCor[f.severidade ?? 'baixa'] }}
                  aria-label={`Foco NASA FIRMS em ${f.municipio ?? 'localização desconhecida'}`}
                />
              </Marker>
            ))}

        {/* Marcadores GOES-16 */}
        {camadasAtivas.has('goes16') &&
          leituraGOES16.map((l) => (
            <Marker
              key={l.id}
              longitude={l.lon}
              latitude={l.lat}
              onClick={() => handleGOESClick(l)}
              anchor="center"
            >
              <button
                className="w-4 h-4 rounded-sm border border-yellow-400 bg-yellow-500/70 cursor-pointer hover:scale-150 transition-transform"
                aria-label={`GOES-16 em ${l.municipio ?? 'localização desconhecida'}`}
              />
            </Marker>
          ))}

        {/* Popup foco */}
        {popupFoco && (
          <Popup
            longitude={popupFoco.lon}
            latitude={popupFoco.lat}
            onClose={() => setPopupFoco(null)}
            closeButton
            anchor="bottom"
          >
            <div className="text-gray-900 text-xs space-y-1 min-w-[160px]">
              <p className="font-bold">{popupFoco.municipio ?? 'Município desconhecido'}</p>
              <p>Fonte: <strong>{popupFoco.fonte}</strong></p>
              <p>Severidade: <strong>{popupFoco.severidade ?? '—'}</strong></p>
              {popupFoco.frp && <p>FRP: <strong>{popupFoco.frp.toFixed(1)} MW</strong></p>}
              {popupFoco.confianca && <p>Confiança: <strong>{popupFoco.confianca.toFixed(0)}%</strong></p>}
              <p className="text-gray-500">{new Date(popupFoco.data_hora).toLocaleString('pt-BR')}</p>
            </div>
          </Popup>
        )}

        {/* Popup GOES-16 */}
        {popupGOES && (
          <Popup
            longitude={popupGOES.lon}
            latitude={popupGOES.lat}
            onClose={() => setPopupGOES(null)}
            closeButton
            anchor="bottom"
          >
            <div className="text-gray-900 text-xs space-y-1 min-w-[160px]">
              <p className="font-bold">GOES-16</p>
              <p>{popupGOES.municipio ?? 'Município desconhecido'}</p>
              {popupGOES.frp_mw && <p>FRP: <strong>{popupGOES.frp_mw.toFixed(1)} MW</strong></p>}
              {popupGOES.temperatura_k && (
                <p>Temp: <strong>{(popupGOES.temperatura_k - 273.15).toFixed(1)}°C</strong></p>
              )}
              {popupGOES.persistencia_horas && (
                <p>Persistência: <strong>{popupGOES.persistencia_horas.toFixed(1)}h</strong></p>
              )}
              <p>Detecções: <strong>{popupGOES.deteccoes_consecutivas}</strong></p>
            </div>
          </Popup>
        )}
      </Map>

      {/* Legenda */}
      <div className="absolute bottom-4 left-4 bg-gray-900/90 border border-gray-700 rounded-lg p-3 text-xs space-y-1.5">
        <p className="font-semibold text-gray-300 mb-1">Severidade</p>
        {Object.entries(severidadeCor).map(([sev, cor]) => (
          <div key={sev} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: cor }} />
            <span className="text-gray-400 capitalize">{sev}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 border-t border-gray-700">
          <span className="w-3 h-3 rounded-sm border border-yellow-400 bg-yellow-500/70" />
          <span className="text-gray-400">GOES-16</span>
        </div>
      </div>
    </div>
  )
}
