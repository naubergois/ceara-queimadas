/**
 * MapaPage — página do mapa interativo com focos e camadas.
 */

import { useQueimadas } from '../hooks/useQueimadas'
import { useQueimadasStore } from '../store/useQueimadasStore'
import MapaQueimadas from '../components/MapaQueimadas'
import CamadasControle from '../components/CamadasControle'
import PainelRiscoMunicipal from '../components/PainelRiscoMunicipal'

export default function MapaPage() {
  useQueimadas()
  const { focos, leituraGOES16, riscos, camadas, carregando, filtroHoras, setFiltroHoras, filtroFonte, setFiltroFonte } =
    useQueimadasStore()

  return (
    <div className="flex h-full">
      {/* Mapa */}
      <div className="flex-1 relative">
        {/* Filtros sobrepostos */}
        <div className="absolute top-4 left-4 z-10 flex gap-2">
          <select
            value={filtroHoras}
            onChange={(e) => setFiltroHoras(Number(e.target.value))}
            className="bg-white/90 border border-slate-200 text-slate-700 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-orange-500"
            aria-label="Filter by time period"
          >
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={48}>Last 48h</option>
            <option value={168}>Last 7 days</option>
          </select>

          <select
            value={filtroFonte ?? ''}
            onChange={(e) => setFiltroFonte(e.target.value || null)}
            className="bg-white/90 border border-slate-200 text-slate-700 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-orange-500"
            aria-label="Filter by source"
          >
            <option value="">All sources</option>
            <option value="INPE">INPE</option>
            <option value="NASA_FIRMS">NASA FIRMS</option>
            <option value="GOES16">GOES-16</option>
          </select>

          {carregando && (
            <div className="bg-white/90 border border-slate-200 rounded-lg px-3 py-2 text-xs text-fire-600">
              Updating...
            </div>
          )}
        </div>

        <MapaQueimadas focos={focos} leituraGOES16={leituraGOES16} />
      </div>

      {/* Painel lateral */}
      <aside className="w-72 bg-stone-50 border-l border-slate-200 overflow-y-auto p-3 space-y-3 shrink-0">
        <CamadasControle camadas={camadas} />
        <PainelRiscoMunicipal riscos={riscos.slice(0, 10)} carregando={carregando} />
      </aside>
    </div>
  )
}
