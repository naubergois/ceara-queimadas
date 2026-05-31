/**
 * TimelineEventos — evolução temporal dos focos de queimada.
 */

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { format, subHours, startOfHour } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import type { Foco } from '../services/api'

interface Props {
  focos: Foco[]
  horas?: number
}

function agruparPorHora(focos: Foco[], horas: number) {
  const agora = new Date()
  const buckets: Record<string, { hora: string; INPE: number; NASA_FIRMS: number; GOES16: number }> = {}

  // Inicializa buckets
  for (let h = horas; h >= 0; h--) {
    const dt = startOfHour(subHours(agora, h))
    const key = dt.toISOString()
    buckets[key] = {
      hora: format(dt, 'HH:mm', { locale: ptBR }),
      INPE: 0,
      NASA_FIRMS: 0,
      GOES16: 0,
    }
  }

  // Conta focos por hora e fonte
  for (const foco of focos) {
    const dt = startOfHour(new Date(foco.data_hora))
    const key = dt.toISOString()
    if (buckets[key]) {
      const fonte = foco.fonte as 'INPE' | 'NASA_FIRMS' | 'GOES16'
      buckets[key][fonte] = (buckets[key][fonte] || 0) + 1
    }
  }

  return Object.values(buckets)
}

export default function TimelineEventos({ focos, horas = 24 }: Props) {
  const dados = agruparPorHora(focos, horas)

  return (
    <section className="card" aria-label="Timeline de eventos de queimada">
      <h2 className="text-sm font-semibold text-white mb-4">Evolução Temporal dos Focos</h2>
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
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="hora"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#d1d5db', fontSize: 12 }}
            itemStyle={{ fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
          <Area type="monotone" dataKey="INPE" stroke="#f97316" fill="url(#gradINPE)" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="NASA_FIRMS" stroke="#3b82f6" fill="url(#gradFIRMS)" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="GOES16" stroke="#eab308" fill="url(#gradGOES)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  )
}
