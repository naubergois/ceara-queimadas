/**
 * BoletimPage — geração e exibição de boletim técnico de queimadas.
 */

import { useState } from 'react'
import { FileText, Download, Loader2 } from 'lucide-react'
import { getBoletim } from '../services/api'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

interface BoletimData {
  boletim: string
  total_eventos: number
  total_alertas: number
}

export default function BoletimPage() {
  const [boletim, setBoletim] = useState<BoletimData | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [municipio, setMunicipio] = useState('')

  const gerar = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await getBoletim(municipio || undefined)
      setBoletim(dados)
    } catch {
      setErro('Erro ao gerar boletim. Verifique a conexão com o servidor.')
    } finally {
      setCarregando(false)
    }
  }

  const baixar = () => {
    if (!boletim) return
    const blob = new Blob([boletim.boletim], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `boletim-queimadas-ceara-${format(new Date(), 'yyyyMMdd-HHmm')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center gap-2">
        <FileText size={20} className="text-orange-400" aria-hidden="true" />
        <div>
          <h1 className="text-lg font-bold text-white">Boletim Técnico</h1>
          <p className="text-sm text-gray-400">Relatório gerado pelo agente LangGraph</p>
        </div>
      </div>

      {/* Controles */}
      <div className="card space-y-3">
        <div className="flex gap-3 flex-wrap">
          <input
            type="text"
            value={municipio}
            onChange={(e) => setMunicipio(e.target.value)}
            placeholder="Município específico (opcional)"
            className="flex-1 min-w-48 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-orange-500"
            aria-label="Filtrar boletim por município"
          />
          <button
            onClick={gerar}
            disabled={carregando}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 disabled:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {carregando ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Gerando...
              </>
            ) : (
              <>
                <FileText size={16} />
                Gerar Boletim
              </>
            )}
          </button>
          {boletim && (
            <button
              onClick={baixar}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg text-sm transition-colors"
              aria-label="Baixar boletim como arquivo de texto"
            >
              <Download size={16} />
              Baixar
            </button>
          )}
        </div>

        {erro && (
          <p className="text-sm text-red-400" role="alert">{erro}</p>
        )}
      </div>

      {/* Boletim */}
      {boletim && (
        <div className="space-y-3">
          {/* Resumo */}
          <div className="grid grid-cols-2 gap-3">
            <div className="card text-center">
              <p className="text-2xl font-bold text-orange-400">{boletim.total_eventos}</p>
              <p className="text-xs text-gray-400">Eventos detectados</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl font-bold text-red-400">{boletim.total_alertas}</p>
              <p className="text-xs text-gray-400">Alertas emitidos</p>
            </div>
          </div>

          {/* Texto do boletim */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white">Conteúdo do Boletim</h2>
              <span className="text-xs text-gray-500">
                Gerado em {format(new Date(), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
              </span>
            </div>
            <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed bg-gray-950 rounded-lg p-4 overflow-auto max-h-[60vh]">
              {boletim.boletim}
            </pre>
          </div>
        </div>
      )}

      {!boletim && !carregando && (
        <div className="text-center py-16 text-gray-500">
          <FileText size={48} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
          <p>Clique em "Gerar Boletim" para criar o relatório técnico</p>
          <p className="text-sm mt-1">O agente LangGraph irá coletar e analisar os dados em tempo real</p>
        </div>
      )}
    </div>
  )
}
