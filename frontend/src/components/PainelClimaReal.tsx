/**
 * PainelClimaReal — exibe dados climáticos reais dos municípios do Ceará.
 * Fonte: Open-Meteo API (gratuita, sem chave).
 */

import { Thermometer, Wind, Droplets, CloudRain, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'
import type { ClimaReal } from '../services/api'

interface Props {
  municipios: ClimaReal[]
  carregando?: boolean
}

function calcularRiscoClimatico(c: ClimaReal): number {
  let score = 0
  if (c.umidade_relativa != null) score += Math.max(0, (50 - c.umidade_relativa) * 0.5)
  if (c.velocidade_vento_ms != null) score += Math.min(c.velocidade_vento_ms * 2, 20)
  if (c.dias_sem_chuva) score += Math.min(c.dias_sem_chuva * 1.5, 30)
  if (c.temperatura_c != null && c.temperatura_c > 35) score += (c.temperatura_c - 35) * 2
  return Math.min(Math.round(score), 100)
}

const RISCO_COR = (r: number) =>
  r >= 70 ? 'text-red-600' : r >= 45 ? 'text-fire-600' : r >= 20 ? 'text-amber-600' : 'text-emerald-600'

const RISCO_BG = (r: number) =>
  r >= 70 ? 'bg-red-50/40 border-red-200/40' : r >= 45 ? 'bg-orange-50/40 border-orange-200/40' : 'bg-slate-100 border-slate-200'

export default function PainelClimaReal({ municipios, carregando }: Props) {
  const ordenados = [...municipios]
    .map(m => ({ ...m, risco: calcularRiscoClimatico(m) }))
    .sort((a, b) => b.risco - a.risco)

  return (
    <section className="card space-y-3" aria-label="Real weather by municipality">
      <div className="flex items-center gap-2">
        <CloudRain size={15} className="text-sky-600" />
        <h2 className="text-sm font-semibold text-slate-900">Real Weather — Open-Meteo</h2>
      </div>

      {carregando ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : ordenados.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-4">No weather data</p>
      ) : (
        <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
          {ordenados.map(m => (
            <div
              key={m.nome}
              className={clsx('rounded-lg p-2.5 border', RISCO_BG(m.risco))}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-slate-700 truncate">{m.nome}</span>
                <div className="flex items-center gap-1 shrink-0">
                  {m.risco >= 70 && <AlertTriangle size={10} className="text-red-600" />}
                  <span className={clsx('text-xs font-bold', RISCO_COR(m.risco))}>
                    {m.risco}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-1">
                <ClimaMini
                  icon={<Thermometer size={10} className="text-red-600" />}
                  valor={m.temperatura_c != null ? `${m.temperatura_c.toFixed(0)}°` : '—'}
                  alerta={(m.temperatura_c ?? 0) >= 35}
                />
                <ClimaMini
                  icon={<Droplets size={10} className="text-sky-600" />}
                  valor={m.umidade_relativa != null ? `${m.umidade_relativa.toFixed(0)}%` : '—'}
                  alerta={(m.umidade_relativa ?? 100) < 40}
                />
                <ClimaMini
                  icon={<Wind size={10} className="text-cyan-400" />}
                  valor={m.velocidade_vento_ms != null ? `${m.velocidade_vento_ms.toFixed(1)}m/s` : '—'}
                  alerta={(m.velocidade_vento_ms ?? 0) >= 7}
                />
                <ClimaMini
                  icon={<CloudRain size={10} className="text-indigo-400" />}
                  valor={`${m.dias_sem_chuva ?? 0}d`}
                  alerta={(m.dias_sem_chuva ?? 0) >= 10}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function ClimaMini({ icon, valor, alerta }: { icon: React.ReactNode; valor: string; alerta: boolean }) {
  return (
    <div className={clsx('flex items-center gap-0.5', alerta ? 'text-orange-300' : 'text-slate-500')}>
      {icon}
      <span className="text-xs">{valor}</span>
    </div>
  )
}
