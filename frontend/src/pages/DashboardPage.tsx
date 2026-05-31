/**
 * DashboardPage — página principal com visão executiva.
 */

import { RefreshCw } from 'lucide-react'
import { useQueimadas } from '../hooks/useQueimadas'
import { useQueimadasStore } from '../store/useQueimadasStore'
import DashboardOperacional from '../components/DashboardOperacional'
import PainelRiscoMunicipal from '../components/PainelRiscoMunicipal'
import TimelineEventos from '../components/TimelineEventos'
import CardAlerta from '../components/CardAlerta'

export default function DashboardPage() {
  const { recarregar } = useQueimadas()
  const { focos, riscos, alertas, leituraGOES16, carregando, erro } = useQueimadasStore()

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-screen-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white">Dashboard Operacional</h1>
          <p className="text-sm text-gray-400">Monitoramento de queimadas — Estado do Ceará</p>
        </div>
        <button
          onClick={recarregar}
          disabled={carregando}
          className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors disabled:opacity-50"
          aria-label="Recarregar dados"
        >
          <RefreshCw size={14} className={carregando ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">Atualizar</span>
        </button>
      </div>

      {/* Erro */}
      {erro && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-3 text-sm text-red-300" role="alert">
          {erro}
        </div>
      )}

      {/* KPIs */}
      <DashboardOperacional
        focos={focos}
        alertas={alertas}
        riscos={riscos}
        leituraGOES16={leituraGOES16}
        carregando={carregando}
      />

      {/* Timeline */}
      <TimelineEventos focos={focos} horas={24} />

      {/* Grid: Risco + Alertas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PainelRiscoMunicipal riscos={riscos} carregando={carregando} />

        {/* Alertas recentes */}
        <section className="card space-y-3" aria-label="Alertas recentes">
          <h2 className="text-sm font-semibold text-white">Alertas Recentes</h2>
          {carregando ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-20 bg-gray-800 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : alertas.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">Nenhum alerta ativo</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {alertas.slice(0, 5).map((a) => (
                <CardAlerta key={a.id_alerta} alerta={a} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
