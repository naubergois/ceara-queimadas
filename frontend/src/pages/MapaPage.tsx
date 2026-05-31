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
            className="bg-gray-900/90 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-orange-500"
            aria-label="Filtrar por período"
          >
            <option value={6}>Últimas 6h</option>
            <option value={24}>Últimas 24h</option>
            <option value={48}>Últimas 48h</option>
            <option value={168}>Últimos 7 dias</option>
          </select>

          <select
            value={filtroFonte ?? ''}
            onChange={(e) => setFiltroFonte(e.target.value || null)}
            className="bg-gray-900/90 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-orange-500"
            aria-label="Filtrar por fonte"
          >
            <option value="">Todas as fontes</option>
            <option value="INPE">INPE</option>
            <option value="NASA_FIRMS">NASA FIRMS</option>
            <option value="GOES16">GOES-16</option>
          </select>

          {carregando && (
            <div className="bg-gray-900/90 border border-gray-700 rounded-lg px-3 py-2 text-xs text-orange-400">
              Atualizando...
            </div>
          )}
        </div>

        <MapaQueimadas focos={focos} leituraGOES16={leituraGOES16} />
      </div>

      {/* Painel lateral */}
      <aside className="w-72 bg-gray-950 border-l border-gray-800 overflow-y-auto p-3 space-y-3 shrink-0">
        <CamadasControle camadas={camadas} />
        <PainelRiscoMunicipal riscos={riscos.slice(0, 10)} carregando={carregando} />
      </aside>
    </div>
  )
}
