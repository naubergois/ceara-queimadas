/**
 * DashboardPage — visão executiva com dados reais NASA FIRMS (mesma fonte do Mapa Real).
 */

import { RefreshCw, Satellite } from 'lucide-react'
import { useQueimadas } from '../hooks/useQueimadas'
import { useFocosReais } from '../hooks/useFocosReais'
import { useAlertasReais } from '../hooks/useAlertasReais'
import { useQueimadasStore } from '../store/useQueimadasStore'
import KPIsFocosReais from '../components/KPIsFocosReais'
import PainelRiscoMunicipal from '../components/PainelRiscoMunicipal'
import TimelineEventos from '../components/TimelineEventos'
import CardAlerta from '../components/CardAlerta'
import StatusFontes from '../components/StatusFontes'

export default function DashboardPage() {
  const { recarregar: recarregarSimulado } = useQueimadas()
  const {
    focos,
    atualizadoEm,
    dias,
    setDias,
    carregando: carregandoReais,
    erro: erroReais,
    recarregar: recarregarReais,
  } = useFocosReais()
  const {
    alertas,
    carregando: carregandoAlertas,
    erro: erroAlertas,
    recarregar: recarregarAlertas,
  } = useAlertasReais()

  const { riscos, carregando: carregandoSimulado } = useQueimadasStore()

  const carregando = carregandoReais || carregandoAlertas || carregandoSimulado

  const atualizarTudo = () => {
    recarregarReais()
    recarregarAlertas()
    recarregarSimulado()
  }

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-screen-2xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Operational Dashboard</h1>
          <p className="page-subtitle mt-1 flex items-center gap-1.5 flex-wrap">
            <Satellite size={14} className="text-fire-600 shrink-0" />
            Real NASA FIRMS data — State of Ceará
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            className="input-field text-xs py-1.5"
            aria-label="Real hotspot time range"
          >
            <option value={1}>Last 24h</option>
            <option value={7}>Last 7 days</option>
          </select>
          <StatusFontes />
          <button
            onClick={atualizarTudo}
            disabled={carregando}
            className="btn-ghost"
            aria-label="Reload data"
          >
            <RefreshCw size={14} className={carregando ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {erroReais && (
        <div className="alert-error" role="alert">
          {erroReais}
        </div>
      )}
      {erroAlertas && (
        <div className="alert-warning" role="alert">
          {erroAlertas}
        </div>
      )}

      <KPIsFocosReais focos={focos} atualizadoEm={atualizadoEm} dias={dias} carregando={carregandoReais} />

      <TimelineEventos focos={focos} horas={dias === 1 ? 24 : 24 * 7} modoReal />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PainelRiscoMunicipal riscos={riscos} carregando={carregandoSimulado} />

        <section className="card space-y-3" aria-label="Recent alerts">
          <h2 className="text-sm font-semibold text-slate-900">Active Alerts</h2>
          <p className="text-xs text-slate-500 -mt-1">
            Generated from NASA FIRMS hotspots and Open-Meteo weather (48h)
          </p>
          {carregandoAlertas ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : alertas.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-4">
              No alerts in this period — conditions are normal, or wait for hotspots to load
            </p>
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
