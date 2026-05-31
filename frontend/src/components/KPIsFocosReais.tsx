/**
 * KPIsFocosReais — métricas dos focos reais coletados do NASA FIRMS.
 */

import { Flame, Satellite, Zap, TrendingUp } from 'lucide-react'
import { clsx } from 'clsx'
import type { FocoReal } from '../services/api'

interface Props {
  focos: FocoReal[]
  atualizadoEm: string | null
  carregando?: boolean
}

export default function KPIsFocosReais({ focos, atualizadoEm, carregando }: Props) {
  const total = focos.length
  const criticos = focos.filter(f => f.severidade === 'critica').length
  const altos = focos.filter(f => f.severidade === 'alta').length
  const frpTotal = focos.reduce((s, f) => s + (f.frp ?? 0), 0)
  const frpMax = Math.max(...focos.map(f => f.frp ?? 0), 0)

  const kpis = [
    {
      label: 'Focos Reais',
      valor: total,
      sub: 'NASA FIRMS 7 dias',
      icon: Flame,
      cor: 'text-orange-400',
      bg: 'bg-orange-950/30',
    },
    {
      label: 'Críticos + Altos',
      valor: criticos + altos,
      sub: `${criticos} críticos, ${altos} altos`,
      icon: Zap,
      cor: criticos > 0 ? 'text-red-400' : 'text-yellow-400',
      bg: criticos > 0 ? 'bg-red-950/30' : 'bg-yellow-950/30',
    },
    {
      label: 'FRP Total',
      valor: `${frpTotal.toFixed(0)} MW`,
      sub: `Máx: ${frpMax.toFixed(1)} MW`,
      icon: TrendingUp,
      cor: 'text-purple-400',
      bg: 'bg-purple-950/30',
    },
    {
      label: 'Satélites',
      valor: new Set(focos.map(f => f.sensor)).size,
      sub: [...new Set(focos.map(f => f.sensor))].join(', ') || '—',
      icon: Satellite,
      cor: 'text-blue-400',
      bg: 'bg-blue-950/30',
    },
  ]

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {kpis.map(({ label, valor, sub, icon: Icon, cor, bg }) => (
          <div key={label} className={clsx('card flex items-center gap-3', bg)}>
            <div className={clsx('p-2 rounded-lg bg-gray-800/50', cor)}>
              <Icon size={18} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              {carregando ? (
                <div className="h-6 w-10 bg-gray-700 rounded animate-pulse mb-1" />
              ) : (
                <p className={clsx('text-xl font-bold leading-tight', cor)}>{valor}</p>
              )}
              <p className="text-xs text-gray-400 truncate">{label}</p>
              <p className="text-xs text-gray-600 truncate">{sub}</p>
            </div>
          </div>
        ))}
      </div>
      {atualizadoEm && (
        <p className="text-xs text-gray-600 text-right">
          Dados coletados em: {new Date(atualizadoEm).toLocaleString('pt-BR')}
        </p>
      )}
    </div>
  )
}
