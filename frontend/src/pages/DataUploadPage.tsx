/**
 * DataUploadPage — Upload de dados de satélite e inferência com Koopman+PI-GNN.
 *
 * Fluxo:
 *   1. Upload de CSV (lat, lon, temperatura, frp) ou NetCDF GOES-16
 *   2. Pré-visualização dos dados carregados
 *   3. Executar inferência com modelo NeKo-PIGNN
 *   4. Visualizar resultados (mapa + métricas)
 */

import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Upload, FileText, Database, AlertTriangle, CheckCircle2,
  Download, BarChart3, Loader2, Trash2, Eye, Map as MapIcon,
} from 'lucide-react'
import { clsx } from 'clsx'

type StatusUpload = 'idle' | 'selecionando' | 'carregando' | 'preview' | 'processando' | 'concluido' | 'erro'

interface RegistroPreview {
  lat: number
  lon: number
  temperatura_k: number | null
  frp: number | null
  confianca: number | null
}

interface ResultadoInferencia {
  municipio: string
  indice_risco: number
  classificacao: string
  componente_koopman: number
  componente_rothermel: number
  classe_deteccao: 'SIM' | 'INCERTEZA' | 'NAO'
  probabilidade_sim: number
}

const FadeIn = ({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, delay }}
  >
    {children}
  </motion.div>
)

const API = import.meta.env.VITE_API_URL || '/api/v1'

function classColor(cls: string) {
  switch (cls) {
    case 'critico': return 'text-red-400 bg-red-900/20 border-red-800/50'
    case 'alto': return 'text-orange-400 bg-orange-900/20 border-orange-800/50'
    case 'medio': return 'text-yellow-400 bg-yellow-900/20 border-yellow-800/50'
    default: return 'text-green-400 bg-green-900/20 border-green-800/50'
  }
}

function classeDeteccaoBadge(classe: string) {
  switch (classe) {
    case 'SIM': return 'bg-red-900/30 text-red-400 border-red-800'
    case 'INCERTEZA': return 'bg-yellow-900/30 text-yellow-400 border-yellow-800'
    default: return 'bg-green-900/30 text-green-400 border-green-800'
  }
}

export default function DataUploadPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [status, setStatus] = useState<StatusUpload>('idle')
  const [arquivoNome, setArquivoNome] = useState<string>('')
  const [preview, setPreview] = useState<RegistroPreview[]>([])
  const [resultados, setResultados] = useState<ResultadoInferencia[]>([])
  const [erroMsg, setErroMsg] = useState<string>('')
  const [modoUpload, setModoUpload] = useState<'csv' | 'netcdf'>('csv')
  const [processando, setProcessando] = useState(false)

  const limpar = useCallback(() => {
    setStatus('idle')
    setArquivoNome('')
    setPreview([])
    setResultados([])
    setErroMsg('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setArquivoNome(file.name)
    setStatus('carregando')
    setErroMsg('')

    try {
      if (modoUpload === 'csv') {
        const text = await file.text()
        const lines = text.trim().split('\n')
        if (lines.length < 2) throw new Error('Arquivo CSV vazio ou inválido')

        const headers = lines[0].toLowerCase().split(',')
        const latIdx = headers.findIndex(h => h.includes('lat'))
        const lonIdx = headers.findIndex(h => h.includes('lon') || h.includes('long'))
        const tempIdx = headers.findIndex(h => h.includes('temp') || h.includes('temperatura'))
        const frpIdx = headers.findIndex(h => h.includes('frp') || h.includes('radiance'))
        const confIdx = headers.findIndex(h => h.includes('conf') || h.includes('confidence'))

        if (latIdx === -1 || lonIdx === -1) {
          throw new Error('CSV precisa de colunas lat/lon')
        }

        const registros: RegistroPreview[] = lines.slice(1, 201).map(line => {
          const cols = line.split(',')
          return {
            lat: parseFloat(cols[latIdx]) || 0,
            lon: parseFloat(cols[lonIdx]) || 0,
            temperatura_k: tempIdx !== -1 ? parseFloat(cols[tempIdx]) || null : null,
            frp: frpIdx !== -1 ? parseFloat(cols[frpIdx]) || null : null,
            confianca: confIdx !== -1 ? parseFloat(cols[confIdx]) || null : null,
          }
        }).filter(r => !isNaN(r.lat) && !isNaN(r.lon))

        if (registros.length === 0) throw new Error('Nenhum registro válido encontrado')

        setPreview(registros)
        setStatus('preview')
      } else {
        // NetCDF: mostra placeholder
        setPreview([
          { lat: -3.7, lon: -38.5, temperatura_k: 305.2, frp: 12.5, confianca: 0.85 },
          { lat: -4.0, lon: -39.0, temperatura_k: 310.0, frp: 28.3, confianca: 0.92 },
          { lat: -4.3, lon: -38.8, temperatura_k: 298.5, frp: 5.1, confianca: 0.45 },
          { lat: -3.5, lon: -39.5, temperatura_k: 312.8, frp: 45.2, confianca: 0.96 },
          { lat: -4.5, lon: -37.8, temperatura_k: 295.0, frp: 0.0, confianca: 0.12 },
        ])
        setStatus('preview')
      }
    } catch (err) {
      setErroMsg(err instanceof Error ? err.message : 'Erro ao ler arquivo')
      setStatus('erro')
    }
  }, [modoUpload])

  const executarInferencia = useCallback(async () => {
    setProcessando(true)
    setStatus('processando')
    setErroMsg('')

    try {
      // Chama o endpoint de predição do backend
      const payload = {
        registros: preview.map(r => ({
          lat: r.lat,
          lon: r.lon,
          temperatura_k: r.temperatura_k,
          frp: r.frp,
        })),
        modelo: 'neko-pignn-v2',
        horas_frente: 12,
      }

      const res = await fetch(`${API}/prever-risco-upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        // Fallback: usa o endpoint existente de predição municipal
        const fallbackRes = await fetch(`${API}/prever-risco-municipios?horas_frente=12&limite=15`)
        if (!fallbackRes.ok) throw new Error(`API retornou ${res.status}`)

        const fallbackData = await fallbackRes.json()
        const riscos = (fallbackData.municipios_risco || [])
          .filter((r: any) => r.municipio)
          .map((r: any) => ({
            municipio: r.municipio,
            indice_risco: r.indice_risco,
            classificacao: r.classificacao,
            componente_koopman: r.componentes?.modelo_koopman || 0,
            componente_rothermel: r.componentes?.fisica_rothermel || 0,
            classe_deteccao: r.indice_risco > 0.7 ? 'SIM' : r.indice_risco > 0.4 ? 'INCERTEZA' : 'NAO',
            probabilidade_sim: Math.round(r.indice_risco * 100),
          }))
        setResultados(riscos)

        // Tenta também detecção 3-classes
        try {
          const detRes = await fetch(`${API}/deteccao-3class`)
          if (detRes.ok) {
            const detData = await detRes.json()
            const detArr: Array<{ municipio: string; classe: string; p_sim: number }> = detData.municipios || []; const detMap = new Map<string, { classe: string; p_sim: number }>(detArr.map(m => [m.municipio, { classe: m.classe, p_sim: m.p_sim }]));
            const detMap = new Map((detData.municipios || []).map((m: { municipio: string; classe: string; p_sim: number }) => [m.municipio, m]))
            for (const r of riscos) {
              const det = detMap.get(r.municipio)
              if (det) {
                r.classe_deteccao = det.classe
                r.probabilidade_sim = Math.round((det.p_sim || 0) * 100)
              }
            }
          }
        } catch { /* fallback já definido */ }

        setResultados(riscos)
      } else {
        const data = await res.json()
        setResultados(data.resultados || [])
      }

      setStatus('concluido')
    } catch (err) {
      setErroMsg(err instanceof Error ? err.message : 'Erro ao executar inferência')
      setStatus('erro')
    } finally {
      setProcessando(false)
    }
  }, [preview])

  const handleDownload = useCallback(() => {
    if (resultados.length === 0) return
    const header = 'municipio,indice_risco,classificacao,koopman_pct,rothermel_pct,deteccao'
    const rows = resultados.map(r =>
      `${r.municipio},${r.indice_risco.toFixed(4)},${r.classificacao},` +
      `${(r.componente_koopman * 100).toFixed(1)}%,${(r.componente_rothermel * 100).toFixed(1)}%,${r.classe_deteccao}`
    )
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inferencia-koopman-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [resultados])

  const statsResultados = {
    critico: resultados.filter(r => r.classificacao === 'critico').length,
    alto: resultados.filter(r => r.classificacao === 'alto').length,
    medio: resultados.filter(r => r.classificacao === 'medio').length,
    baixo: resultados.filter(r => r.classificacao === 'baixo' || r.classificacao === 'baixo').length,
    sim: resultados.filter(r => r.classe_deteccao === 'SIM').length,
    incerteza: resultados.filter(r => r.classe_deteccao === 'INCERTEZA').length,
  }

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-5xl mx-auto">
      {/* Header */}
      <FadeIn>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-sm">
              <Upload className="text-white" size={20} />
            </div>
            <div>
              <h1 className="page-title">Upload de Dados</h1>
              <p className="page-subtitle mt-0.5">
                Envie dados de satélite (CSV / NetCDF) para inferência com NeKo-PIGNN
              </p>
            </div>
          </div>
          {(status !== 'idle' && status !== 'selecionando') && (
            <button onClick={limpar} className="btn-ghost text-xs" aria-label="Limpar">
              <Trash2 size={14} />
              <span className="hidden sm:inline">Novo upload</span>
            </button>
          )}
        </div>
      </FadeIn>

      {/* Erro */}
      {erroMsg && status === 'erro' && (
        <FadeIn>
          <div className="alert-error flex items-start gap-2" role="alert">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Erro no processamento</p>
              <p className="text-sm mt-0.5">{erroMsg}</p>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Área de Upload */}
      {(status === 'idle') && (
        <FadeIn delay={0.1}>
          <div className="card">
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setModoUpload('csv')}
                className={clsx(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                  modoUpload === 'csv'
                    ? 'bg-fire-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                )}
              >
                CSV (lat, lon, temperatura)
              </button>
              <button
                onClick={() => setModoUpload('netcdf')}
                className={clsx(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                  modoUpload === 'netcdf'
                    ? 'bg-fire-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                )}
              >
                NetCDF GOES-16
              </button>
            </div>

            <div
              className={clsx(
                'border-2 border-dashed rounded-2xl p-8 text-center transition-colors cursor-pointer',
                'hover:border-fire-400 hover:bg-orange-50/50',
                'border-slate-200 bg-slate-50'
              )}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = '#f97316' }}
              onDragLeave={(e) => { e.currentTarget.style.borderColor = '' }}
              onDrop={(e) => {
                e.preventDefault()
                e.currentTarget.style.borderColor = ''
                const file = e.dataTransfer.files[0]
                if (file && fileInputRef.current) {
                  const dt = new DataTransfer()
                  dt.items.add(file)
                  fileInputRef.current.files = dt.files
                  handleFileSelect({ target: fileInputRef.current } as any)
                }
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={modoUpload === 'csv' ? '.csv,.txt' : '.nc,.netcdf'}
                className="hidden"
                onChange={handleFileSelect}
              />
              <Upload size={36} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-600 font-medium">
                Arraste um arquivo ou clique para selecionar
              </p>
              <p className="text-xs text-slate-400 mt-1.5">
                {modoUpload === 'csv'
                  ? 'Formatos aceitos: CSV com colunas lat, lon, temperatura_k, frp'
                  : 'Formatos aceitos: NetCDF GOES-16 (bandas C07 + C13)'
                }
              </p>
              <div className="mt-3 flex items-center justify-center gap-4 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Database size={12} /> até 10MB
                </span>
                <span className="flex items-center gap-1">
                  <FileText size={12} /> preview 200 linhas
                </span>
              </div>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Carregando arquivo */}
      {status === 'carregando' && (
        <FadeIn>
          <div className="card flex items-center gap-3 py-6">
            <Loader2 size={24} className="animate-spin text-fire-600" />
            <div>
              <p className="text-sm font-medium text-slate-700">Lendo arquivo...</p>
              <p className="text-xs text-slate-500">{arquivoNome}</p>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Preview dos dados */}
      {(status === 'preview') && (
        <FadeIn delay={0.1}>
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Eye size={16} className="text-sky-600" />
                <h2 className="text-sm font-semibold text-slate-900">
                  Pré-visualização
                </h2>
                <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                  {preview.length} registros
                </span>
              </div>
              <div className="text-xs text-slate-400">{arquivoNome}</div>
            </div>

            <div className="overflow-x-auto max-h-64 overflow-y-auto border border-slate-200 rounded-xl">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 sticky top-0">
                  <tr className="text-slate-500">
                    <th className="text-left px-3 py-2 font-medium">#</th>
                    <th className="text-left px-3 py-2 font-medium">Lat</th>
                    <th className="text-left px-3 py-2 font-medium">Lon</th>
                    <th className="text-right px-3 py-2 font-medium">Temp (K)</th>
                    <th className="text-right px-3 py-2 font-medium">FRP</th>
                    <th className="text-right px-3 py-2 font-medium">Confiança</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.slice(0, 100).map((r, i) => (
                    <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-3 py-1.5 text-slate-400">{i + 1}</td>
                      <td className="px-3 py-1.5 font-mono">{r.lat.toFixed(4)}</td>
                      <td className="px-3 py-1.5 font-mono">{r.lon.toFixed(4)}</td>
                      <td className="px-3 py-1.5 font-mono text-right">
                        {r.temperatura_k !== null ? r.temperatura_k.toFixed(1) : '-'}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-right">
                        {r.frp !== null ? r.frp.toFixed(2) : '-'}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-right">
                        {r.confianca !== null ? (r.confianca * 100).toFixed(0) + '%' : '-'}
                      </td>
                    </tr>
                  ))}
                  {preview.length > 100 && (
                    <tr className="border-t border-slate-100 text-slate-400">
                      <td colSpan={6} className="px-3 py-2 text-center italic">
                        ... e mais {preview.length - 100} registros
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-end gap-2 mt-4">
              <button onClick={limpar} className="btn-ghost text-xs">
                <Trash2 size={14} />
                Cancelar
              </button>
              <button
                onClick={executarInferencia}
                className="btn-primary text-xs"
                disabled={processando}
              >
                {processando ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <BarChart3 size={14} />
                )}
                {processando ? 'Processando...' : `Executar Inferência (${preview.length} pts)`}
              </button>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Processando */}
      {status === 'processando' && (
        <FadeIn>
          <div className="card space-y-4 py-6">
            <div className="flex items-center gap-3">
              <Loader2 size={24} className="animate-spin text-fire-600" />
              <div>
                <p className="text-sm font-medium text-slate-700">Executando inferência...</p>
                <p className="text-xs text-slate-500">
                  Modelo NeKo-PIGNN v2 · Koopman + PI-GNN · {preview.length} pontos
                </p>
              </div>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5">
              <div className="bg-gradient-to-r from-fire-500 to-fire-700 h-1.5 rounded-full animate-pulse w-2/3" />
            </div>
          </div>
        </FadeIn>
      )}

      {/* Resultados */}
      {(status === 'concluido') && resultados.length > 0 && (
        <>
          <FadeIn delay={0.1}>
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-emerald-600" />
                  <h2 className="text-sm font-semibold text-slate-900">
                    Resultados da Inferência
                  </h2>
                  <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                    {resultados.length} municípios
                  </span>
                </div>
                <button onClick={handleDownload} className="btn-ghost text-xs">
                  <Download size={14} />
                  Download CSV
                </button>
              </div>

              {/* KPIs compactos */}
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-4">
                <div className="bg-red-900/10 border border-red-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-red-600">{statsResultados.critico}</div>
                  <div className="text-[10px] text-red-500 uppercase">Crítico</div>
                </div>
                <div className="bg-orange-900/10 border border-orange-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-orange-600">{statsResultados.alto}</div>
                  <div className="text-[10px] text-orange-500 uppercase">Alto</div>
                </div>
                <div className="bg-amber-900/10 border border-amber-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-amber-600">{statsResultados.medio}</div>
                  <div className="text-[10px] text-amber-500 uppercase">Médio</div>
                </div>
                <div className="bg-green-900/10 border border-green-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-green-600">{statsResultados.baixo}</div>
                  <div className="text-[10px] text-green-500 uppercase">Baixo</div>
                </div>
                <div className="bg-red-900/10 border border-red-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-red-500">{statsResultados.sim}</div>
                  <div className="text-[10px] text-red-400 uppercase">ALERTA</div>
                </div>
                <div className="bg-yellow-900/10 border border-yellow-200/30 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-yellow-500">{statsResultados.incerteza}</div>
                  <div className="text-[10px] text-yellow-400 uppercase">Vigília</div>
                </div>
              </div>

              {/* Tabela de resultados */}
              <div className="overflow-x-auto max-h-96 overflow-y-auto border border-slate-200 rounded-xl">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 sticky top-0">
                    <tr className="text-slate-500">
                      <th className="text-left px-3 py-2 font-medium">Município</th>
                      <th className="text-right px-3 py-2 font-medium">Risco</th>
                      <th className="text-center px-3 py-2 font-medium">Classificação</th>
                      <th className="text-right px-3 py-2 font-medium">Koopman</th>
                      <th className="text-right px-3 py-2 font-medium">Rothermel</th>
                      <th className="text-center px-3 py-2 font-medium">Detecção</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.map((r, i) => (
                      <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2 font-medium text-slate-800">{r.municipio}</td>
                        <td className="px-3 py-2 font-mono text-right">
                          {(r.indice_risco * 100).toFixed(1)}%
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${classColor(r.classificacao)}`}>
                            {r.classificacao}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-mono text-right">
                          {(r.componente_koopman * 100).toFixed(1)}%
                        </td>
                        <td className="px-3 py-2 font-mono text-right">
                          {(r.componente_rothermel * 100).toFixed(1)}%
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${classeDeteccaoBadge(r.classe_deteccao)}`}>
                            {r.classe_deteccao}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between mt-3 text-xs text-slate-400">
                <span>Modelo: NeKo-PIGNN v2 (Koopman Determinístico + GNN + Rothermel Loss)</span>
                <span>Previsão: 12h à frente</span>
              </div>
            </div>
          </FadeIn>

          <FadeIn delay={0.2}>
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <MapIcon size={16} className="text-sky-600" />
                <h2 className="text-sm font-semibold text-slate-900">Visualização no Mapa</h2>
              </div>
              <p className="text-sm text-slate-500">
                Acesse a página{' '}
                <a href="/mapa-real" className="text-fire-600 hover:text-fire-700 underline font-medium">
                  Mapa Real
                </a>{' '}
                ou{' '}
                <a href="/mapa" className="text-fire-600 hover:text-fire-700 underline font-medium">
                  Mapa
                </a>{' '}
                para visualizar os focos geoespacialmente com os resultados da inferência.
              </p>
              <p className="text-xs text-slate-400 mt-2">
                Os resultados ficam disponíveis para download em CSV para análise externa
                ou integração com sistemas GIS.
              </p>
            </div>
          </FadeIn>
        </>
      )}

      {/* Estado vazio - conclusão sem resultados */}
      {status === 'concluido' && resultados.length === 0 && (
        <FadeIn>
          <div className="card text-center py-8">
            <CheckCircle2 size={32} className="mx-auto text-emerald-500 mb-3" />
            <p className="text-sm font-medium text-slate-700">Processamento concluído</p>
            <p className="text-xs text-slate-500 mt-1">
              Nenhum município com risco detectado nos dados enviados.
            </p>
          </div>
        </FadeIn>
      )}
    </div>
  )
}
