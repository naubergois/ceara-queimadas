/**
 * KPIsFocosReais — métricas dos focos reais coletados do NASA FIRMS.
 */

import { Flame, Satellite, Zap, TrendingUp } from 'lucide-react'
import { clsx } from 'clsx'
import type { FocoReal } from '../services/api'

interface Props {
  focos: FocoReal[]
  atualizadoEm: string | null
  dias?: number
  carregando?: boolean
}

export default function KPIsFocosReais({ focos, atualizadoEm, dias = 7, carregando }: Props) {
  const periodoLabel = dias === 1 ? 'últimas 24h' : `últimos ${dias} dias`
  const total = focos.length
  const criticos = focos.filter(f => f.severidade === 'critica').length
  const altos = focos.filter(f => f.severidade === 'alta').length
  const frpTotal = focos.reduce((s, f) => s + (f.frp ?? 0), 0)
  const frpMax = Math.max(...focos.map(f => f.frp ?? 0), 0)

  const kpis = [
    {
      label: 'Focos Reais',
      valor: total,
      sub: `NASA FIRMS · ${periodoLabel}`,
      icon: Flame,
      cor: 'text-fire-600',
      bg: 'bg-orange-50 border-orange-100',
    },
    {
      label: 'Críticos + Altos',
      valor: criticos + altos,
      sub: `${criticos} críticos, ${altos} altos`,
      icon: Zap,
      cor: criticos > 0 ? 'text-red-700' : 'text-amber-700',
      bg: criticos > 0 ? 'bg-red-50 border-red-100' : 'bg-amber-50 border-amber-100',
    },
    {
      label: 'FRP Total',
      valor: `${frpTotal.toFixed(0)} MW`,
      sub: `Máx: ${frpMax.toFixed(1)} MW`,
      icon: TrendingUp,
      cor: 'text-violet-700',
      bg: 'bg-violet-50 border-violet-100',
    },
    {
      label: 'Satélites',
      valor: new Set(focos.map(f => f.sensor)).size,
      sub: [...new Set(focos.map(f => f.sensor))].join(', ') || '—',
      icon: Satellite,
      cor: 'text-sky-700',
      bg: 'bg-sky-50 border-sky-100',
    },
  ]

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {kpis.map(({ label, valor, sub, icon: Icon, cor, bg }) => (
          <div key={label} className={clsx('card flex items-center gap-3 border', bg)}>
            <div className={clsx('p-2 rounded-lg bg-slate-100/50', cor)}>
              <Icon size={18} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              {carregando ? (
                <div className="h-6 w-10 bg-slate-200 rounded animate-pulse mb-1" />
              ) : (
                <p className={clsx('text-xl font-bold leading-tight', cor)}>{valor}</p>
              )}
              <p className="text-xs text-slate-500 truncate">{label}</p>
              <p className="text-xs text-slate-400 truncate">{sub}</p>
            </div>
          </div>
        ))}
      </div>
      {atualizadoEm && (
        <p className="text-xs text-slate-400 text-right">
          Dados coletados em: {new Date(atualizadoEm).toLocaleString('pt-BR')}
        </p>
      )}
    </div>
  )
}
