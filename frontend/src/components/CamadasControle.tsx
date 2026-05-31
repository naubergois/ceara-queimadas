/**
 * CamadasControle — painel para ativar/desativar camadas do mapa.
 */

import { Layers } from 'lucide-react'
import { clsx } from 'clsx'
import type { CamadaMapa } from '../services/api'
import { useQueimadasStore } from '../store/useQueimadasStore'

interface Props {
  camadas: CamadaMapa[]
}

const tipoLabel: Record<string, string> = {
  pontos: '●',
  poligonos: '▬',
  raster: '▦',
  heatmap: '◉',
}

export default function CamadasControle({ camadas }: Props) {
  const toggleCamada = useQueimadasStore((s) => s.toggleCamada)

  return (
    <section className="card space-y-2" aria-label="Controle de camadas do mapa">
      <div className="flex items-center gap-2 mb-1">
        <Layers size={16} className="text-blue-400" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-white">Camadas</h2>
      </div>

      <ul className="space-y-1.5">
        {camadas.map((camada) => (
          <li key={camada.id}>
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={camada.ativo}
                onChange={() => toggleCamada(camada.id)}
                className="w-4 h-4 rounded accent-orange-500 cursor-pointer"
                aria-label={`Camada ${camada.nome}`}
              />
              <span
                className={clsx(
                  'text-xs transition-colors',
                  camada.ativo ? 'text-gray-200' : 'text-gray-500',
                )}
              >
                <span className="mr-1 text-gray-500">{tipoLabel[camada.tipo]}</span>
                {camada.nome}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  )
}
