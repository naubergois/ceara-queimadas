/**
 * ChatAgente — interface conversacional com o agente LangChain ReAct.
 * Permite perguntas em linguagem natural sobre queimadas no Ceará.
 */

import { useRef, useState } from 'react'
import { Send, Bot, User, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { perguntarAgente, type RespostaAgente } from '../services/api'
import { format } from 'date-fns'
import { enUS } from 'date-fns/locale'

interface Mensagem {
  id: string
  tipo: 'usuario' | 'agente'
  texto: string
  resposta?: RespostaAgente
  timestamp: Date
  carregando?: boolean
}

const SUGESTOES = [
  'Which municipalities have the highest risk today?',
  'Is there a hotspot near a conservation unit?',
  'Did GOES-16 confirm fire growth in the latest images?',
  'Which hotspots appeared in the last 3 hours?',
  'Generate a bulletin for Civil Defense.',
  'Compare INPE hotspots with NASA FIRMS.',
]

export default function ChatAgente() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      id: '0',
      tipo: 'agente',
      texto: 'Hello! I am the Ceará wildfire monitoring agent. I can query active hotspots, weather data, GOES-16, and calculate risks. How can I help?',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [enviando, setEnviando] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const enviar = async (pergunta: string) => {
    if (!pergunta.trim() || enviando) return

    const idUser = Date.now().toString()
    const idAgent = (Date.now() + 1).toString()

    setMensagens((prev) => [
      ...prev,
      { id: idUser, tipo: 'usuario', texto: pergunta, timestamp: new Date() },
      { id: idAgent, tipo: 'agente', texto: '', timestamp: new Date(), carregando: true },
    ])
    setInput('')
    setEnviando(true)
    scrollBottom()

    try {
      const resposta = await perguntarAgente(pergunta)
      setMensagens((prev) =>
        prev.map((m) =>
          m.id === idAgent
            ? { ...m, texto: resposta.resposta, resposta, carregando: false }
            : m,
        ),
      )
    } catch {
      setMensagens((prev) =>
        prev.map((m) =>
          m.id === idAgent
            ? { ...m, texto: 'Failed to query the agent. Please try again.', carregando: false }
            : m,
        ),
      )
    } finally {
      setEnviando(false)
      scrollBottom()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      enviar(input)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Mensagens */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite" aria-label="Agent conversation">
        {mensagens.map((msg) => (
          <MensagemItem key={msg.id} mensagem={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Sugestões */}
      <div className="px-4 pb-2 flex gap-2 overflow-x-auto scrollbar-hide">
        {SUGESTOES.map((s) => (
          <button
            key={s}
            onClick={() => enviar(s)}
            disabled={enviando}
            className="shrink-0 text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-full transition-colors disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-200">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about wildfires in Ceará..."
            rows={2}
            disabled={enviando}
            className="flex-1 bg-slate-100 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 resize-none focus:outline-none focus:border-orange-500 disabled:opacity-50"
            aria-label="Question field"
          />
          <button
            onClick={() => enviar(input)}
            disabled={!input.trim() || enviando}
            className="p-3 bg-orange-600 hover:bg-orange-500 disabled:bg-slate-200 disabled:text-slate-500 text-white rounded-xl transition-colors"
            aria-label="Send question"
          >
            {enviando ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1.5">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-componente de mensagem
// ---------------------------------------------------------------------------

function MensagemItem({ mensagem }: { mensagem: Mensagem }) {
  const [expandido, setExpandido] = useState(false)
  const isAgente = mensagem.tipo === 'agente'

  return (
    <div className={clsx('flex gap-3', isAgente ? 'items-start' : 'items-start flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
          isAgente ? 'bg-orange-600' : 'bg-slate-200',
        )}
        aria-hidden="true"
      >
        {isAgente ? <Bot size={16} className="text-white" /> : <User size={16} className="text-slate-600" />}
      </div>

      {/* Balão */}
      <div className={clsx('max-w-[80%] space-y-2', isAgente ? '' : 'items-end')}>
        <div
          className={clsx(
            'rounded-2xl px-4 py-3 text-sm leading-relaxed',
            isAgente ? 'bg-slate-100 text-slate-700' : 'bg-orange-600 text-white',
          )}
        >
          {mensagem.carregando ? (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader2 size={14} className="animate-spin" />
              <span>Querying tools...</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{mensagem.texto}</p>
          )}
        </div>

        {/* Evidências e metadados */}
        {mensagem.resposta && !mensagem.carregando && (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandido(!expandido)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs text-slate-500 hover:bg-slate-100 transition-colors"
              aria-expanded={expandido}
            >
              <span>
                Confidence: {(mensagem.resposta.nivel_confianca * 100).toFixed(0)}% ·{' '}
                {mensagem.resposta.ferramentas_usadas.length} tools queried
              </span>
              {expandido ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {expandido && (
              <div className="px-3 pb-3 space-y-2 text-xs">
                {mensagem.resposta.recomendacao_operacional && (
                  <div>
                    <p className="text-fire-600 font-medium mb-0.5">Recommendation</p>
                    <p className="text-slate-600">{mensagem.resposta.recomendacao_operacional}</p>
                  </div>
                )}
                {mensagem.resposta.evidencias.length > 0 && (
                  <div>
                    <p className="text-sky-600 font-medium mb-0.5">Evidence</p>
                    <ul className="space-y-0.5">
                      {mensagem.resposta.evidencias.map((e, i) => (
                        <li key={i} className="text-slate-500 truncate">{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {mensagem.resposta.fontes.length > 0 && (
                  <div>
                    <p className="text-emerald-600 font-medium mb-0.5">Sources</p>
                    <p className="text-slate-500">{mensagem.resposta.fontes.join(', ')}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <time className="text-xs text-slate-400 px-1">
          {format(mensagem.timestamp, 'HH:mm', { locale: enUS })}
        </time>
      </div>
    </div>
  )
}
