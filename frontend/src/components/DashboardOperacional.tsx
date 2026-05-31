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
      label: 'Focos Ativos',
      valor: focos24h,
      sub: 'últimas 24h',
      icon: Flame,
      cor: 'text-orange-400',
    },
    {
      label: 'Emergências',
      valor: alertasEmergencia,
      sub: 'alertas críticos',
      icon: AlertTriangle,
      cor: alertasEmergencia > 0 ? 'text-red-400' : 'text-gray-500',
    },
    {
      label: 'Municípios Críticos',
      valor: municipiosCriticos,
      sub: 'risco crítico',
      icon: CloudRain,
      cor: municipiosCriticos > 0 ? 'text-red-400' : 'text-green-400',
    },
    {
      label: 'GOES-16',
      valor: goes16Ativos,
      sub: 'pixels com fogo',
      icon: Satellite,
      cor: 'text-yellow-400',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" role="region" aria-label="KPIs operacionais">
      {kpis.map((kpi) => {
        const Icon = kpi.icon
        return (
          <div key={kpi.label} className="card flex items-center gap-3">
            <div className={clsx('p-2 rounded-lg bg-gray-800', kpi.cor)}>
              <Icon size={20} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              {carregando ? (
                <div className="h-6 w-12 bg-gray-700 rounded animate-pulse mb-1" />
              ) : (
                <p className={clsx('text-2xl font-bold', kpi.cor)}>{kpi.valor}</p>
              )}
              <p className="text-xs text-gray-400 truncate">{kpi.label}</p>
              <p className="text-xs text-gray-600">{kpi.sub}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
