/**
 * DashboardOperacional — visão executiva com KPIs principais.
 */

import { Flame, AlertTriangle, Satellite, CloudRain } from 'lucide-react'
import { clsx } from 'clsx'
import type { Alerta, Foco, LeituraGOES16, RiscoMunicipal } from '../services/api'

interface Props {
  focos: Foco[]
  alertas: Alerta[]
  riscos: RiscoMunicipal[]
  leituraGOES16: LeituraGOES16[]
  carregando?: boolean
}

interface KPI {
  label: string
  valor: string | number
  sub: string
  icon: React.ElementType
  cor: string
}

export default function DashboardOperacional({ focos, alertas, riscos, leituraGOES16, carregando }: Props) {
  const focos24h = focos.length
  const alertasEmergencia = alertas.filter((a) => a.nivel === 'emergencia').length
  const municipiosCriticos = riscos.filter((r) => r.classificacao === 'critico').length
  const goes16Ativos = leituraGOES16.length

  const kpis: KPI[] = [
    {
      label: 'Active Hotspots',
      valor: focos24h,
      sub: 'last 24h',
      icon: Flame,
      cor: 'text-fire-600',
    },
    {
      label: 'Emergencies',
      valor: alertasEmergencia,
      sub: 'critical alerts',
      icon: AlertTriangle,
      cor: alertasEmergencia > 0 ? 'text-red-600' : 'text-slate-500',
    },
    {
      label: 'Critical Municipalities',
      valor: municipiosCriticos,
      sub: 'critical risk',
      icon: CloudRain,
      cor: municipiosCriticos > 0 ? 'text-red-600' : 'text-emerald-600',
    },
    {
      label: 'GOES-16',
      valor: goes16Ativos,
      sub: 'fire pixels',
      icon: Satellite,
      cor: 'text-amber-600',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" role="region" aria-label="Operational KPIs">
      {kpis.map((kpi) => {
        const Icon = kpi.icon
        return (
          <div key={kpi.label} className="card flex items-center gap-3">
            <div className={clsx('p-2 rounded-lg bg-slate-100', kpi.cor)}>
              <Icon size={20} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              {carregando ? (
                <div className="h-6 w-12 bg-slate-200 rounded animate-pulse mb-1" />
              ) : (
                <p className={clsx('text-2xl font-bold', kpi.cor)}>{kpi.valor}</p>
              )}
              <p className="text-xs text-slate-500 truncate">{kpi.label}</p>
              <p className="text-xs text-slate-400">{kpi.sub}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
