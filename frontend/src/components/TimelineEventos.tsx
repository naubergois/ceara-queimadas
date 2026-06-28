/**
 * TimelineEventos — evolução temporal dos focos de queimada.
 */

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { format, subHours, startOfHour, subDays } from 'date-fns'
import { enUS } from 'date-fns/locale'
import type { Foco, FocoReal } from '../services/api'

type FocoTimeline = Foco | FocoReal

interface Props {
  focos: FocoTimeline[]
  horas?: number
  /** Quando true, agrupa focos NASA FIRMS reais (fonte única) */
  modoReal?: boolean
}

function normalizarFonte(fonte: string | undefined, modoReal: boolean): 'INPE' | 'NASA_FIRMS' | 'GOES16' {
  if (modoReal) return 'NASA_FIRMS'
  const f = (fonte ?? '').toUpperCase()
  if (f.includes('INPE')) return 'INPE'
  if (f.includes('GOES')) return 'GOES16'
  if (f.includes('NASA') || f.includes('FIRMS')) return 'NASA_FIRMS'
  return 'NASA_FIRMS'
}

function agruparPorHora(focos: FocoTimeline[], horas: number, modoReal: boolean) {
  const agora = new Date()
  const inicio = horas > 48 ? subDays(agora, Math.ceil(horas / 24)) : subHours(agora, horas)
  const buckets: Record<string, { hora: string; INPE: number; NASA_FIRMS: number; GOES16: number }> = {}

  const passoHoras = horas > 48 ? 6 : 1
  const totalBuckets = Math.ceil(horas / passoHoras)

  for (let i = totalBuckets; i >= 0; i--) {
    const dt = startOfHour(subHours(agora, i * passoHoras))
    if (dt < inicio) continue
    const key = dt.toISOString()
    buckets[key] = {
      hora: format(dt, horas > 48 ? 'MM/dd HH:mm' : 'HH:mm', { locale: enUS }),
      INPE: 0,
      NASA_FIRMS: 0,
      GOES16: 0,
    }
  }

  for (const foco of focos) {
    const dt = new Date(foco.data_hora)
    if (dt < inicio) continue
    const bucketKey = startOfHour(dt).toISOString()
    const key = buckets[bucketKey]
      ? bucketKey
      : Object.keys(buckets).find((k) => Math.abs(new Date(k).getTime() - dt.getTime()) < 3600_000 * passoHoras)
    if (key && buckets[key]) {
      const fonte = normalizarFonte('fonte' in foco ? foco.fonte : undefined, modoReal)
      buckets[key][fonte] = (buckets[key][fonte] || 0) + 1
    }
  }

  return Object.values(buckets)
}

export default function TimelineEventos({ focos, horas = 24, modoReal = false }: Props) {
  const dados = agruparPorHora(focos, horas, modoReal)
  const titulo = modoReal
    ? 'NASA FIRMS hotspot evolution'
    : 'Hotspot timeline'

  return (
    <section className="card" aria-label="Wildfire event timeline">
      <h2 className="text-sm font-semibold text-slate-900 mb-4">{titulo}</h2>
      {dados.every((d) => d.INPE === 0 && d.NASA_FIRMS === 0 && d.GOES16 === 0) && focos.length === 0 ? (
        <p className="text-sm text-slate-500 text-center py-8">No hotspots in the selected period</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={dados} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="gradINPE" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradFIRMS" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradGOES" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#eab308" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="hora"
              tick={{ fill: '#64748b', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                color: '#0f172a',
              }}
              labelStyle={{ fontSize: 12 }}
              itemStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
            {!modoReal && (
              <Area type="monotone" dataKey="INPE" stroke="#f97316" fill="url(#gradINPE)" strokeWidth={2} dot={false} />
            )}
            <Area type="monotone" dataKey="NASA_FIRMS" stroke="#3b82f6" fill="url(#gradFIRMS)" strokeWidth={2} dot={false} />
            {!modoReal && (
              <Area type="monotone" dataKey="GOES16" stroke="#eab308" fill="url(#gradGOES)" strokeWidth={2} dot={false} />
            )}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </section>
  )
}
