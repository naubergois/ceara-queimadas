/**
 * MapaRealPage — página principal com mapa de focos REAIS do NASA FIRMS.
 *
 * Layout:
 *   [Lista de focos] | [Mapa interativo] | [Painel explicação agente]
 *
 * Fluxo:
 *   1. Carrega focos reais do NASA FIRMS via backend
 *   2. Exibe no mapa com marcadores por severidade
 *   3. Ao clicar num foco → agente busca clima real e explica o foco
 */

import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Layers, List, Thermometer, Map } from 'lucide-react'
import { clsx } from 'clsx'
import { useFocosReais } from '../hooks/useFocosReais'
import { getClimaReal, type FocoReal, type ClimaReal } from '../services/api'
import MapaFocosReais from '../components/MapaFocosReais'
import ListaFocosReais from '../components/ListaFocosReais'
import PainelExplicacaoFoco from '../components/PainelExplicacaoFoco'
import KPIsFocosReais from '../components/KPIsFocosReais'
import PainelClimaReal from '../components/PainelClimaReal'
import StatusFontes from '../components/StatusFontes'

type PainelLateral = 'lista' | 'clima'

export default function MapaRealPage() {
  const {
    focos,
    atualizadoEm,
    dias,
    setDias,
    carregando: carregandoFocos,
    erro,
    recarregar: recarregarFocos,
  } = useFocosReais()

  const [clima, setClima] = useState<ClimaReal[]>([])
  const [carregandoClima, setCarregandoClima] = useState(false)

  const [focoSelecionado, setFocoSelecionado] = useState<FocoReal | null>(null)
  const [painelLateral, setPainelLateral] = useState<PainelLateral>('lista')
  const [mostrarHeatmap, setMostrarHeatmap] = useState(false)
  const [mostrarClusters, setMostrarClusters] = useState(true)

  const carregarClima = useCallback(async () => {
    setCarregandoClima(true)
    try {
      const respClima = await getClimaReal()
      setClima(respClima.municipios)
    } catch {
      /* clima é complementar */
    } finally {
      setCarregandoClima(false)
    }
  }, [])

  useEffect(() => {
    carregarClima()
  }, [carregarClima])

  const carregar = useCallback(() => {
    recarregarFocos()
    carregarClima()
  }, [recarregarFocos, carregarClima])

  const carregando = carregandoFocos || carregandoClima

  const handleSelecionarFoco = useCallback((foco: FocoReal) => {
    setFocoSelecionado(foco)
  }, [])

  const handleFecharExplicacao = useCallback(() => {
    setFocoSelecionado(null)
  }, [])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Barra superior ── */}
      <div className="toolbar px-4 py-3 flex items-center gap-3 flex-wrap shrink-0">
        <div className="flex items-center gap-2">
          <Map size={16} className="text-fire-600" />
          <span className="text-sm font-semibold text-slate-900">Focos Reais — Ceará</span>
          <span className="text-xs text-slate-500">NASA FIRMS + Open-Meteo</span>
        </div>

        {/* Período */}
        <select
          value={dias}
          onChange={e => setDias(Number(e.target.value))}
          className="input-field text-xs py-1.5"
          aria-label="Período de coleta"
        >
          <option value={1}>Últimas 24h</option>
          <option value={7}>Últimos 7 dias</option>
        </select>

        {/* Toggles de camadas */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={mostrarHeatmap}
              onChange={e => setMostrarHeatmap(e.target.checked)}
              className="w-3.5 h-3.5 accent-orange-500"
            />
            <span className="text-xs text-slate-500">Heatmap</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={mostrarClusters}
              onChange={e => setMostrarClusters(e.target.checked)}
              className="w-3.5 h-3.5 accent-orange-500"
            />
            <span className="text-xs text-slate-500">Clusters</span>
          </label>
        </div>

        {/* Status das fontes */}
        <div className="ml-auto">
          <StatusFontes />
        </div>

        {/* Atualizar */}
        <button
          onClick={carregar}
          disabled={carregando}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg text-xs transition-colors disabled:opacity-50"
          aria-label="Recarregar dados reais"
        >
          <RefreshCw size={12} className={carregando ? 'animate-spin' : ''} />
          Atualizar
        </button>
      </div>

      {/* ── KPIs ── */}
      <div className="px-4 py-2 border-b border-slate-200 bg-stone-50 shrink-0">
        {erro ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-800" role="alert">
            {erro}
          </div>
        ) : (
          <KPIsFocosReais focos={focos} atualizadoEm={atualizadoEm} dias={dias} carregando={carregando} />
        )}
      </div>

      {/* ── Corpo principal ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Painel esquerdo: lista ou clima ── */}
        <div className="w-64 bg-stone-50 border-r border-slate-200 flex flex-col shrink-0">
          {/* Tabs */}
          <div className="flex border-b border-slate-200">
            <button
              onClick={() => setPainelLateral('lista')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors',
                painelLateral === 'lista'
                  ? 'text-fire-600 border-b-2 border-orange-500 bg-white'
                  : 'text-slate-500 hover:text-slate-600'
              )}
              aria-pressed={painelLateral === 'lista'}
            >
              <List size={12} />
              Focos ({focos.length})
            </button>
            <button
              onClick={() => setPainelLateral('clima')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors',
                painelLateral === 'clima'
                  ? 'text-sky-600 border-b-2 border-blue-500 bg-white'
                  : 'text-slate-500 hover:text-slate-600'
              )}
              aria-pressed={painelLateral === 'clima'}
            >
              <Thermometer size={12} />
              Clima
            </button>
          </div>

          {/* Conteúdo do painel */}
          <div className="flex-1 overflow-hidden">
            {painelLateral === 'lista' ? (
              <ListaFocosReais
                focos={focos}
                focoSelecionado={focoSelecionado}
                onSelecionarFoco={handleSelecionarFoco}
                carregando={carregando}
              />
            ) : (
              <div className="p-3 overflow-y-auto h-full">
                <PainelClimaReal municipios={clima} carregando={carregando} />
              </div>
            )}
          </div>
        </div>

        {/* ── Mapa ── */}
        <div className="flex-1 relative">
          <MapaFocosReais
            focos={focos}
            focoSelecionado={focoSelecionado}
            onSelecionarFoco={handleSelecionarFoco}
            mostrarHeatmap={mostrarHeatmap}
            mostrarClusters={mostrarClusters}
          />

          {/* Instrução overlay quando nenhum foco selecionado */}
          {!focoSelecionado && !carregando && focos.length > 0 && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-white/90 border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-600 backdrop-blur-sm pointer-events-none">
              Clique em um foco para ver a análise do agente IA
            </div>
          )}

          {carregando && (
            <div className="absolute inset-0 flex items-center justify-center bg-stone-50/50 backdrop-blur-sm">
              <div className="bg-white border border-slate-200 rounded-xl px-6 py-4 flex items-center gap-3">
                <RefreshCw size={18} className="animate-spin text-fire-600" />
                <div>
                  <p className="text-sm text-slate-800 font-medium">Coletando dados reais...</p>
                  <p className="text-xs text-slate-500">NASA FIRMS + Open-Meteo — a primeira carga pode levar até 1 min</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Painel direito: explicação do agente ── */}
        {focoSelecionado && (
          <PainelExplicacaoFoco
            foco={focoSelecionado}
            onFechar={handleFecharExplicacao}
          />
        )}
      </div>
    </div>
  )
}
