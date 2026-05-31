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
import { getFocosReais, getClimaReal, type FocoReal, type ClimaReal } from '../services/api'
import MapaFocosReais from '../components/MapaFocosReais'
import ListaFocosReais from '../components/ListaFocosReais'
import PainelExplicacaoFoco from '../components/PainelExplicacaoFoco'
import KPIsFocosReais from '../components/KPIsFocosReais'
import PainelClimaReal from '../components/PainelClimaReal'
import StatusFontes from '../components/StatusFontes'

type PainelLateral = 'lista' | 'clima'

export default function MapaRealPage() {
  const [focos, setFocos] = useState<FocoReal[]>([])
  const [clima, setClima] = useState<ClimaReal[]>([])
  const [atualizadoEm, setAtualizadoEm] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [focoSelecionado, setFocoSelecionado] = useState<FocoReal | null>(null)
  const [painelLateral, setPainelLateral] = useState<PainelLateral>('lista')
  const [mostrarHeatmap, setMostrarHeatmap] = useState(false)
  const [mostrarClusters, setMostrarClusters] = useState(true)
  const [dias, setDias] = useState(7)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [respFocos, respClima] = await Promise.all([
        getFocosReais(dias),
        getClimaReal(),
      ])
      setFocos(respFocos.focos)
      setAtualizadoEm(respFocos.atualizado_em)
      setClima(respClima.municipios)
    } catch (e) {
      const msg =
        e instanceof Error && e.message.includes('timeout')
          ? 'A primeira carga dos dados reais pode levar até 2 minutos. Tente atualizar novamente.'
          : 'Não foi possível carregar os dados reais. Verifique se o backend está ativo (em dev: uvicorn na porta 8000).'
      setErro(msg)
    } finally {
      setCarregando(false)
    }
  }, [dias])

  useEffect(() => { carregar() }, [carregar])

  const handleSelecionarFoco = useCallback((foco: FocoReal) => {
    setFocoSelecionado(foco)
  }, [])

  const handleFecharExplicacao = useCallback(() => {
    setFocoSelecionado(null)
  }, [])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Barra superior ── */}
      <div className="px-4 py-2 border-b border-gray-800 bg-gray-900 flex items-center gap-3 flex-wrap shrink-0">
        <div className="flex items-center gap-2">
          <Map size={16} className="text-orange-400" />
          <span className="text-sm font-semibold text-white">Focos Reais — Ceará</span>
          <span className="text-xs text-gray-500">NASA FIRMS + Open-Meteo</span>
        </div>

        {/* Período */}
        <select
          value={dias}
          onChange={e => setDias(Number(e.target.value))}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-orange-500"
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
            <span className="text-xs text-gray-400">Heatmap</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={mostrarClusters}
              onChange={e => setMostrarClusters(e.target.checked)}
              className="w-3.5 h-3.5 accent-orange-500"
            />
            <span className="text-xs text-gray-400">Clusters</span>
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
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-xs transition-colors disabled:opacity-50"
          aria-label="Recarregar dados reais"
        >
          <RefreshCw size={12} className={carregando ? 'animate-spin' : ''} />
          Atualizar
        </button>
      </div>

      {/* ── KPIs ── */}
      <div className="px-4 py-2 border-b border-gray-800 bg-gray-950 shrink-0">
        {erro ? (
          <div className="bg-red-950 border border-red-800 rounded-xl p-3 text-sm text-red-300" role="alert">
            {erro}
          </div>
        ) : (
          <KPIsFocosReais focos={focos} atualizadoEm={atualizadoEm} carregando={carregando} />
        )}
      </div>

      {/* ── Corpo principal ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Painel esquerdo: lista ou clima ── */}
        <div className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col shrink-0">
          {/* Tabs */}
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setPainelLateral('lista')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors',
                painelLateral === 'lista'
                  ? 'text-orange-400 border-b-2 border-orange-500 bg-gray-900'
                  : 'text-gray-500 hover:text-gray-300'
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
                  ? 'text-blue-400 border-b-2 border-blue-500 bg-gray-900'
                  : 'text-gray-500 hover:text-gray-300'
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
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-gray-900/90 border border-gray-700 rounded-xl px-4 py-2 text-xs text-gray-300 backdrop-blur-sm pointer-events-none">
              Clique em um foco para ver a análise do agente IA
            </div>
          )}

          {carregando && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-950/50 backdrop-blur-sm">
              <div className="bg-gray-900 border border-gray-700 rounded-xl px-6 py-4 flex items-center gap-3">
                <RefreshCw size={18} className="animate-spin text-orange-400" />
                <div>
                  <p className="text-sm text-white font-medium">Coletando dados reais...</p>
                  <p className="text-xs text-gray-400">NASA FIRMS + Open-Meteo — a primeira carga pode levar até 1 min</p>
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
