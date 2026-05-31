/**
 * ChatAgente — interface conversacional com o agente LangChain ReAct.
 * Permite perguntas em linguagem natural sobre queimadas no Ceará.
 */

import { useRef, useState } from 'react'
import { Send, Bot, User, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { perguntarAgente, type RespostaAgente } from '../services/api'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

interface Mensagem {
  id: string
  tipo: 'usuario' | 'agente'
  texto: string
  resposta?: RespostaAgente
  timestamp: Date
  carregando?: boolean
}

const SUGESTOES = [
  'Quais municípios estão com maior risco hoje?',
  'Existe algum foco próximo a unidade de conservação?',
  'O GOES-16 confirmou crescimento do fogo nas últimas imagens?',
  'Quais focos apareceram nas últimas 3 horas?',
  'Gere um boletim para a Defesa Civil.',
  'Compare os focos do INPE com os do NASA FIRMS.',
]

export default function ChatAgente() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      id: '0',
      tipo: 'agente',
      texto: 'Olá! Sou o agente de monitoramento de queimadas do Ceará. Posso consultar focos ativos, dados climáticos, GOES-16 e calcular riscos. Como posso ajudar?',
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
            ? { ...m, texto: 'Erro ao consultar o agente. Tente novamente.', carregando: false }
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
      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite" aria-label="Conversa com o agente">
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
            className="shrink-0 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-full transition-colors disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pergunte sobre queimadas no Ceará..."
            rows={2}
            disabled={enviando}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:border-orange-500 disabled:opacity-50"
            aria-label="Campo de pergunta"
          />
          <button
            onClick={() => enviar(input)}
            disabled={!input.trim() || enviando}
            className="p-3 bg-orange-600 hover:bg-orange-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl transition-colors"
            aria-label="Enviar pergunta"
          >
            {enviando ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-1.5">Enter para enviar · Shift+Enter para nova linha</p>
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
          isAgente ? 'bg-orange-600' : 'bg-gray-700',
        )}
        aria-hidden="true"
      >
        {isAgente ? <Bot size={16} className="text-white" /> : <User size={16} className="text-gray-300" />}
      </div>

      {/* Balão */}
      <div className={clsx('max-w-[80%] space-y-2', isAgente ? '' : 'items-end')}>
        <div
          className={clsx(
            'rounded-2xl px-4 py-3 text-sm leading-relaxed',
            isAgente ? 'bg-gray-800 text-gray-200' : 'bg-orange-600 text-white',
          )}
        >
          {mensagem.carregando ? (
            <div className="flex items-center gap-2 text-gray-400">
              <Loader2 size={14} className="animate-spin" />
              <span>Consultando ferramentas...</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{mensagem.texto}</p>
          )}
        </div>

        {/* Evidências e metadados */}
        {mensagem.resposta && !mensagem.carregando && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandido(!expandido)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:bg-gray-800 transition-colors"
              aria-expanded={expandido}
            >
              <span>
                Confiança: {(mensagem.resposta.nivel_confianca * 100).toFixed(0)}% ·{' '}
                {mensagem.resposta.ferramentas_usadas.length} ferramentas consultadas
              </span>
              {expandido ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {expandido && (
              <div className="px-3 pb-3 space-y-2 text-xs">
                {mensagem.resposta.recomendacao_operacional && (
                  <div>
                    <p className="text-orange-400 font-medium mb-0.5">Recomendação</p>
                    <p className="text-gray-300">{mensagem.resposta.recomendacao_operacional}</p>
                  </div>
                )}
                {mensagem.resposta.evidencias.length > 0 && (
                  <div>
                    <p className="text-blue-400 font-medium mb-0.5">Evidências</p>
                    <ul className="space-y-0.5">
                      {mensagem.resposta.evidencias.map((e, i) => (
                        <li key={i} className="text-gray-400 truncate">{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {mensagem.resposta.fontes.length > 0 && (
                  <div>
                    <p className="text-green-400 font-medium mb-0.5">Fontes</p>
                    <p className="text-gray-400">{mensagem.resposta.fontes.join(', ')}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <time className="text-xs text-gray-600 px-1">
          {format(mensagem.timestamp, 'HH:mm', { locale: ptBR })}
        </time>
      </div>
    </div>
  )
}
