/**
 * AlertasPage — alertas reais (NASA FIRMS + Open-Meteo) com filtros por nível.
 */

import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useAlertasReais } from '../hooks/useAlertasReais'
import { useFocosReais } from '../hooks/useFocosReais'
import CardAlerta from '../components/CardAlerta'

const NIVEIS = ['todos', 'emergencia', 'alerta', 'atencao', 'informativo'] as const

const NIVEL_LABELS: Record<string, string> = {
  todos: 'All',
  emergencia: 'Emergency',
  alerta: 'Alert',
  atencao: 'Attention',
  informativo: 'Informational',
}

export default function AlertasPage() {
  useFocosReais()
  const { alertas, carregando, erro, recarregar } = useAlertasReais()
  const [filtroNivel, setFiltroNivel] = useState<string>('todos')

  const alertasFiltrados =
    filtroNivel === 'todos' ? alertas : alertas.filter((a) => a.nivel === filtroNivel)

  const contagem = {
    emergencia: alertas.filter((a) => a.nivel === 'emergencia').length,
    alerta: alertas.filter((a) => a.nivel === 'alerta').length,
    atencao: alertas.filter((a) => a.nivel === 'atencao').length,
    informativo: alertas.filter((a) => a.nivel === 'informativo').length,
  }

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="page-title">Wildfire Alerts</h1>
          <p className="page-subtitle mt-1">
            {alertas.length} alerts · NASA FIRMS + Open-Meteo · last 48h
          </p>
        </div>
        <button
          type="button"
          onClick={recarregar}
          disabled={carregando}
          className="btn-ghost"
          aria-label="Refresh alerts"
        >
          <RefreshCw size={14} className={carregando ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {erro && (
        <div className="alert-error" role="alert">
          {erro}
        </div>
      )}

      <div className="flex gap-2 flex-wrap text-xs text-slate-500">
        <span className="text-red-700 font-medium">{contagem.emergencia} emergency</span>
        <span>·</span>
        <span className="text-orange-700 font-medium">{contagem.alerta} alert</span>
        <span>·</span>
        <span className="text-amber-700 font-medium">{contagem.atencao} attention</span>
        <span>·</span>
        <span>{contagem.informativo} informational</span>
      </div>

      <div className="flex gap-2 flex-wrap" role="group" aria-label="Filter alerts by level">
        {NIVEIS.map((nivel) => (
          <button
            key={nivel}
            type="button"
            onClick={() => setFiltroNivel(nivel)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors capitalize ${
              filtroNivel === nivel
                ? 'bg-fire-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
            aria-pressed={filtroNivel === nivel}
          >
            {NIVEL_LABELS[nivel]}
          </button>
        ))}
      </div>

      {carregando ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : alertasFiltrados.length === 0 ? (
        <div className="text-center py-16 text-slate-500 card">
          <p className="text-lg font-medium text-slate-700">No alerts in this filter</p>
          <p className="text-sm mt-1">
            Alerts are generated automatically when there are FIRMS hotspots or elevated weather risk
          </p>
        </div>
      ) : (
        <div className="space-y-3" role="list" aria-label="Alert list">
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
