/**
 * PainelExplicacaoFoco — painel lateral que exibe a explicação do agente
 * para um foco selecionado no mapa. Mostra clima real, intensidade,
 * raciocínio do agente e recomendação operacional.
 */

import { useEffect, useState } from 'react'
import {
  X, Bot, Loader2, Thermometer, Wind, Droplets,
  CloudRain, Flame, Satellite, Clock, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle, Info
} from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import axios from 'axios'
import { getExplicacaoFoco, type FocoReal, type FocoComExplicacao, type ClimaReal } from '../services/api'

interface Props {
  foco: FocoReal | null
  onFechar: () => void
}

const severidadeConfig = {
  baixa:   { cor: 'text-green-400',  bg: 'bg-green-950 border-green-800',  label: 'Baixa' },
  media:   { cor: 'text-yellow-400', bg: 'bg-yellow-950 border-yellow-800', label: 'Média' },
  alta:    { cor: 'text-orange-400', bg: 'bg-orange-950 border-orange-800', label: 'Alta' },
  critica: { cor: 'text-red-400',    bg: 'bg-red-950 border-red-800',       label: 'Crítica' },
}

export default function PainelExplicacaoFoco({ foco, onFechar }: Props) {
  const [dados, setDados] = useState<FocoComExplicacao | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [expandirPassos, setExpandirPassos] = useState(false)

  useEffect(() => {
    if (!foco) { setDados(null); return }
    setCarregando(true)
    setErro(null)
    setDados(null)
    setExpandirPassos(false)

    getExplicacaoFoco(foco.id)
      .then(setDados)
      .catch((e: unknown) => {
        if (axios.isAxiosError(e)) {
          if (e.response?.status === 404) {
            setErro('Foco não encontrado no servidor. Clique em Atualizar no mapa e selecione o foco novamente.')
            return
          }
          if (e.code === 'ECONNABORTED' || e.message.includes('timeout')) {
            setErro('A análise demorou demais. Tente novamente em alguns segundos.')
            return
          }
        }
        setErro('Erro ao consultar o agente. Verifique se o backend está ativo.')
      })
      .finally(() => setCarregando(false))
  }, [foco?.id])

  if (!foco) return null

  const sev = severidadeConfig[foco.severidade] ?? severidadeConfig.baixa
  const tempC = foco.temperatura_k ? (foco.temperatura_k - 273.15).toFixed(1) : null

  return (
    <aside
      className="w-96 bg-gray-900 border-l border-gray-800 flex flex-col h-full overflow-hidden"
      aria-label="Painel de explicação do foco"
    >
      {/* Header */}
      <div className={clsx('px-4 py-3 border-b border-gray-800 flex items-start justify-between gap-2', sev.bg)}>
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <Flame size={16} className={sev.cor} />
            <span className={clsx('text-sm font-bold', sev.cor)}>
              {foco.municipio ?? 'Localização no Ceará'}
            </span>
            <span className={clsx('text-xs px-2 py-0.5 rounded-full border', sev.bg, sev.cor)}>
              {sev.label}
            </span>
          </div>
          <p className="text-xs text-gray-400">
            {foco.lat.toFixed(4)}, {foco.lon.toFixed(4)} · {foco.sensor}
          </p>
        </div>
        <button
          onClick={onFechar}
          className="p-1 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-white transition-colors shrink-0"
          aria-label="Fechar painel"
        >
          <X size={16} />
        </button>
      </div>

      {/* Dados do foco */}
      <div className="px-4 py-3 border-b border-gray-800 grid grid-cols-2 gap-2">
        <MetricaItem
          icon={<Satellite size={13} className="text-blue-400" />}
          label="Satélite"
          valor={foco.satelite}
        />
        <MetricaItem
          icon={<Clock size={13} className="text-gray-400" />}
          label="Detecção"
          valor={format(new Date(foco.data_hora), 'dd/MM HH:mm', { locale: ptBR })}
        />
        {foco.frp != null && (
          <MetricaItem
            icon={<Flame size={13} className="text-orange-400" />}
            label="FRP"
            valor={`${foco.frp.toFixed(1)} MW`}
          />
        )}
        {tempC && (
          <MetricaItem
            icon={<Thermometer size={13} className="text-red-400" />}
            label="Temp. pixel"
            valor={`${tempC}°C`}
          />
        )}
        <MetricaItem
          icon={<CheckCircle size={13} className="text-green-400" />}
          label="Confiança"
          valor={`${foco.confianca.toFixed(0)}%`}
        />
        <MetricaItem
          icon={<Info size={13} className="text-gray-400" />}
          label="Período"
          valor={foco.daynight === 'D' ? 'Diurno' : foco.daynight === 'N' ? 'Noturno' : '—'}
        />
      </div>

      {/* Conteúdo principal — scroll */}
      <div className="flex-1 overflow-y-auto">
        {carregando && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="relative">
              <Bot size={32} className="text-orange-500" />
              <Loader2 size={16} className="animate-spin text-orange-400 absolute -bottom-1 -right-1" />
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-300 font-medium">Agente analisando...</p>
              <p className="text-xs text-gray-500 mt-1">Consultando clima real e intensidade</p>
            </div>
            <div className="flex gap-1 mt-2">
              {['Clima', 'Intensidade', 'Diagnóstico'].map((s, i) => (
                <span
                  key={s}
                  className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded-full animate-pulse"
                  style={{ animationDelay: `${i * 0.3}s` }}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {erro && (
          <div className="m-4 bg-red-950 border border-red-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={16} className="text-red-400" />
              <span className="text-sm font-medium text-red-300">Erro na análise</span>
            </div>
            <p className="text-xs text-red-400">{erro}</p>
          </div>
        )}

        {dados && !carregando && (
          <div className="p-4 space-y-4">
            {/* Clima real */}
            {dados.analise_agente?.clima && Object.keys(dados.analise_agente.clima).length > 0 && (
              <PainelClima clima={dados.analise_agente.clima as ClimaReal} />
            )}

            {/* Explicação do agente */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Bot size={14} className="text-orange-400" />
                <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
                  Análise do Agente
                </span>
                <span className="text-xs text-gray-600 ml-auto">
                  {(dados.analise_agente.nivel_confianca * 100).toFixed(0)}% confiança
                </span>
              </div>
              <div className="bg-gray-800 rounded-xl p-3">
                <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                  {dados.analise_agente.explicacao}
                </p>
              </div>
            </div>

            {/* Ferramentas usadas */}
            {dados.analise_agente.ferramentas_usadas?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {dados.analise_agente.ferramentas_usadas.map(f => (
                  <span key={f} className="text-xs bg-blue-950 text-blue-300 border border-blue-800 px-2 py-0.5 rounded-full">
                    {f.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}

            {/* Passos de raciocínio (expansível) */}
            {dados.analise_agente.passos_raciocinio?.length > 0 && (
              <div className="border border-gray-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandirPassos(!expandirPassos)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:bg-gray-800 transition-colors"
                  aria-expanded={expandirPassos}
                >
                  <span>Raciocínio do agente ({dados.analise_agente.passos_raciocinio.length} passos)</span>
                  {expandirPassos ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {expandirPassos && (
                  <div className="px-3 pb-3 space-y-1.5 bg-gray-950">
                    {dados.analise_agente.passos_raciocinio.map((p, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-xs text-gray-600 shrink-0 mt-0.5">{i + 1}.</span>
                        <p className="text-xs text-gray-400 leading-relaxed">{p}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Timestamp */}
            <p className="text-xs text-gray-600 text-right">
              Análise gerada em{' '}
              {format(new Date(dados.analise_agente.gerado_em), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Sub-componentes
// ---------------------------------------------------------------------------

function MetricaItem({ icon, label, valor }: { icon: React.ReactNode; label: string; valor: string }) {
  return (
    <div className="flex items-center gap-1.5">
      {icon}
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-xs font-medium text-gray-200 truncate">{valor}</p>
      </div>
    </div>
  )
}

function PainelClima({ clima }: { clima: ClimaReal }) {
  const itens = [
    {
      icon: <Thermometer size={14} className="text-red-400" />,
      label: 'Temperatura',
      valor: clima.temperatura_c != null ? `${clima.temperatura_c.toFixed(1)}°C` : null,
      alerta: (clima.temperatura_c ?? 0) >= 35,
    },
    {
      icon: <Droplets size={14} className="text-blue-400" />,
      label: 'Umidade',
      valor: clima.umidade_relativa != null ? `${clima.umidade_relativa.toFixed(0)}%` : null,
      alerta: (clima.umidade_relativa ?? 100) < 40,
    },
    {
      icon: <Wind size={14} className="text-cyan-400" />,
      label: 'Vento',
      valor: clima.velocidade_vento_ms != null ? `${clima.velocidade_vento_ms.toFixed(1)} m/s` : null,
      alerta: (clima.velocidade_vento_ms ?? 0) >= 7,
    },
    {
      icon: <CloudRain size={14} className="text-indigo-400" />,
      label: 'Dias sem chuva',
      valor: clima.dias_sem_chuva != null ? `${clima.dias_sem_chuva} dias` : null,
      alerta: (clima.dias_sem_chuva ?? 0) >= 10,
    },
  ].filter(i => i.valor != null)

  if (itens.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <CloudRain size={14} className="text-blue-400" />
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
          Clima Real (Open-Meteo)
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {itens.map(({ icon, label, valor, alerta }) => (
          <div
            key={label}
            className={clsx(
              'rounded-lg p-2.5 border',
              alerta
                ? 'bg-orange-950/50 border-orange-800/50'
                : 'bg-gray-800 border-gray-700'
            )}
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              {icon}
              <span className="text-xs text-gray-400">{label}</span>
              {alerta && <AlertTriangle size={10} className="text-orange-400 ml-auto" />}
            </div>
            <p className={clsx('text-sm font-bold', alerta ? 'text-orange-300' : 'text-white')}>
              {valor}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
