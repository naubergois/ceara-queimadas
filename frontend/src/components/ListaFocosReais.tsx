/**
 * ListaFocosReais — lista lateral dos focos reais com filtros e ordenação.
 * Ao clicar num foco, centraliza o mapa e abre o painel de explicação.
 */

import { useMemo, useState } from 'react'
import { Flame, Filter, ArrowUpDown, Satellite } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import type { FocoReal } from '../services/api'

interface Props {
  focos: FocoReal[]
  focoSelecionado: FocoReal | null
  onSelecionarFoco: (foco: FocoReal) => void
  carregando?: boolean
}

type Ordenacao = 'recente' | 'frp' | 'severidade'

const SEV_ORDEM = { critica: 4, alta: 3, media: 2, baixa: 1 }
const SEV_COR = {
  baixa:   'bg-green-500',
  media:   'bg-yellow-500',
  alta:    'bg-orange-500',
  critica: 'bg-red-500',
}
const SEV_TEXT = {
  baixa:   'text-emerald-600',
  media:   'text-amber-600',
  alta:    'text-fire-600',
  critica: 'text-red-600',
}

export default function ListaFocosReais({ focos, focoSelecionado, onSelecionarFoco, carregando }: Props) {
  const [filtroSev, setFiltroSev] = useState<string>('todos')
  const [ordenacao, setOrdenacao] = useState<Ordenacao>('recente')
  const [busca, setBusca] = useState('')

  const focosFiltrados = useMemo(() => {
    let lista = [...focos]

    if (filtroSev !== 'todos') lista = lista.filter(f => f.severidade === filtroSev)
    if (busca.trim()) {
      const q = busca.toLowerCase()
      lista = lista.filter(f =>
        f.municipio?.toLowerCase().includes(q) ||
        f.sensor.toLowerCase().includes(q) ||
        f.satelite.toLowerCase().includes(q)
      )
    }

    lista.sort((a, b) => {
      if (ordenacao === 'frp') return (b.frp ?? 0) - (a.frp ?? 0)
      if (ordenacao === 'severidade') return (SEV_ORDEM[b.severidade] ?? 0) - (SEV_ORDEM[a.severidade] ?? 0)
      return new Date(b.data_hora).getTime() - new Date(a.data_hora).getTime()
    })

    return lista
  }, [focos, filtroSev, ordenacao, busca])

  return (
    <div className="flex flex-col h-full">
      {/* Controles */}
      <div className="p-3 space-y-2 border-b border-slate-200">
        <input
          type="text"
          value={busca}
          onChange={e => setBusca(e.target.value)}
          placeholder="Buscar município ou sensor..."
          className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:border-orange-500"
          aria-label="Buscar focos"
        />
        <div className="flex gap-1.5">
          {/* Filtro severidade */}
          <div className="flex items-center gap-1 flex-1">
            <Filter size={11} className="text-slate-500 shrink-0" />
            <select
              value={filtroSev}
              onChange={e => setFiltroSev(e.target.value)}
              className="flex-1 bg-slate-100 border border-slate-200 rounded text-xs text-slate-600 px-1.5 py-1 focus:outline-none"
              aria-label="Filtrar por severidade"
            >
              <option value="todos">Todas</option>
              <option value="critica">Crítica</option>
              <option value="alta">Alta</option>
              <option value="media">Média</option>
              <option value="baixa">Baixa</option>
            </select>
          </div>
          {/* Ordenação */}
          <div className="flex items-center gap-1 flex-1">
            <ArrowUpDown size={11} className="text-slate-500 shrink-0" />
            <select
              value={ordenacao}
              onChange={e => setOrdenacao(e.target.value as Ordenacao)}
              className="flex-1 bg-slate-100 border border-slate-200 rounded text-xs text-slate-600 px-1.5 py-1 focus:outline-none"
              aria-label="Ordenar focos"
            >
              <option value="recente">Mais recente</option>
              <option value="frp">Maior FRP</option>
              <option value="severidade">Severidade</option>
            </select>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          {focosFiltrados.length} de {focos.length} focos
        </p>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto" role="list" aria-label="Lista de focos reais">
        {carregando ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : focosFiltrados.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500">
            <Flame size={32} className="mb-2 opacity-30" />
            <p className="text-sm">Nenhum foco encontrado</p>
          </div>
        ) : (
          focosFiltrados.map(foco => (
            <button
              key={foco.id}
              onClick={() => onSelecionarFoco(foco)}
              className={clsx(
                'w-full text-left px-3 py-2.5 border-b border-slate-200/50 transition-colors',
                focoSelecionado?.id === foco.id
                  ? 'bg-orange-50/40 border-l-2 border-l-orange-500'
                  : 'hover:bg-slate-100/50'
              )}
              role="listitem"
              aria-selected={focoSelecionado?.id === foco.id}
            >
              <div className="flex items-start gap-2">
                {/* Indicador de severidade */}
                <div className={clsx('w-2 h-2 rounded-full mt-1.5 shrink-0', SEV_COR[foco.severidade])} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs font-medium text-slate-700 truncate">
                      {foco.municipio ?? `${foco.lat.toFixed(3)}, ${foco.lon.toFixed(3)}`}
                    </span>
                    <span className={clsx('text-xs font-bold shrink-0', SEV_TEXT[foco.severidade])}>
                      {foco.severidade}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 mt-0.5">
                    <div className="flex items-center gap-1">
                      <Satellite size={10} className="text-slate-500" />
                      <span className="text-xs text-slate-500">{foco.sensor}</span>
                    </div>
                    {foco.frp != null && (
                      <div className="flex items-center gap-1">
                        <Flame size={10} className="text-orange-500" />
                        <span className="text-xs text-slate-500">{foco.frp.toFixed(1)} MW</span>
                      </div>
                    )}
                    <span className="text-xs text-slate-400 ml-auto">
                      {format(new Date(foco.data_hora), 'dd/MM HH:mm', { locale: ptBR })}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
