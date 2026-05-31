/**
 * AlertasPage — listagem completa de alertas ativos com filtros.
 */

import { useState } from 'react'
import { useQueimadas } from '../hooks/useQueimadas'
import { useQueimadasStore } from '../store/useQueimadasStore'
import CardAlerta from '../components/CardAlerta'

const NIVEIS = ['todos', 'emergencia', 'alerta', 'atencao', 'informativo'] as const

export default function AlertasPage() {
  useQueimadas()
  const { alertas, carregando } = useQueimadasStore()
  const [filtroNivel, setFiltroNivel] = useState<string>('todos')

  const alertasFiltrados =
    filtroNivel === 'todos' ? alertas : alertas.filter((a) => a.nivel === filtroNivel)

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white">Alertas de Queimadas</h1>
          <p className="text-sm text-gray-400">{alertas.length} alertas nas últimas 48h</p>
        </div>
      </div>

      {/* Filtros de nível */}
      <div className="flex gap-2 flex-wrap" role="group" aria-label="Filtrar alertas por nível">
        {NIVEIS.map((nivel) => (
          <button
            key={nivel}
            onClick={() => setFiltroNivel(nivel)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors capitalize ${
              filtroNivel === nivel
                ? 'bg-orange-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
            aria-pressed={filtroNivel === nivel}
          >
            {nivel}
          </button>
        ))}
      </div>

      {/* Lista */}
      {carregando ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : alertasFiltrados.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg">Nenhum alerta encontrado</p>
          <p className="text-sm mt-1">Tente outro filtro ou aguarde a próxima atualização</p>
        </div>
      ) : (
        <div className="space-y-3" role="list" aria-label="Lista de alertas">
          {alertasFiltrados.map((a) => (
            <div key={a.id_alerta} role="listitem">
              <CardAlerta alerta={a} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
