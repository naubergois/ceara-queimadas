/**
 * PainelRiscoMunicipal — ranking dos municípios com maior risco de queimada.
 */

import { clsx } from 'clsx'
import { TrendingUp } from 'lucide-react'
import type { RiscoMunicipal } from '../services/api'

interface Props {
  riscos: RiscoMunicipal[]
  carregando?: boolean
}

const classConfig = {
  baixo: 'badge-baixo',
  moderado: 'badge-moderado',
  alto: 'badge-alto',
  critico: 'badge-critico',
}

const barColor = {
  baixo: 'bg-green-500',
  moderado: 'bg-yellow-500',
  alto: 'bg-orange-500',
  critico: 'bg-red-500',
}

export default function PainelRiscoMunicipal({ riscos, carregando }: Props) {
  return (
    <section className="card space-y-3" aria-label="Ranking de risco municipal">
      <div className="flex items-center gap-2 mb-1">
        <TrendingUp size={16} className="text-fire-600" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-slate-900">Risco por Município</h2>
      </div>

      {carregando ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 bg-slate-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : riscos.length === 0 ? (
        <p className="text-sm text-slate-500 text-center py-4">Nenhum dado disponível</p>
      ) : (
        <ol className="space-y-2">
          {riscos.map((r) => (
            <li key={r.municipio} className="space-y-1">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs text-slate-500 w-5 shrink-0">{r.posicao}.</span>
                  <span className="text-sm text-slate-700 truncate">{r.municipio}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-slate-500">{r.focos_24h} focos</span>
                  <span className={classConfig[r.classificacao]}>{r.classificacao}</span>
                </div>
              </div>
              {/* Barra de risco */}
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden" role="progressbar" aria-valuenow={r.indice_risco} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className={clsx('h-full rounded-full transition-all duration-500', barColor[r.classificacao])}
                  style={{ width: `${r.indice_risco}%` }}
                />
              </div>
              {/* Justificativa */}
              {r.justificativa && (
                <p className="text-xs text-slate-500 leading-tight">{r.justificativa}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
