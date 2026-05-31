/**
 * ChatPesquisa — chat RAG (FAISS) sobre a pesquisa e o funcionamento da aplicação.
 */

import { useEffect, useRef, useState } from 'react'
import { Send, Bot, User, Loader2, BookOpen, FileText } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { chatPesquisa, getStatusPesquisa, type RespostaPesquisa } from '../services/api'

interface Mensagem {
  id: string
  tipo: 'usuario' | 'agente'
  texto: string
  resposta?: RespostaPesquisa
  timestamp: Date
  carregando?: boolean
}

const SUGESTOES = [
  'Qual é o objetivo da pesquisa deste gêmeo digital?',
  'Como funciona a arquitetura do sistema?',
  'Quais fontes de dados reais estão implementadas?',
  'Explique o pipeline LangGraph e os agentes de IA.',
  'Como faço deploy na EC2?',
  'Qual a diferença entre o mapa real e o chat operacional?',
]

export default function ChatPesquisa() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      id: '0',
      tipo: 'agente',
      texto:
        'Olá! Sou o guia da aplicação. Pergunte sobre a pesquisa, a arquitetura, as fontes de dados (NASA FIRMS, Open-Meteo), os agentes DeepSeek ou como usar o sistema.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [indicePronto, setIndicePronto] = useState<boolean | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getStatusPesquisa()
      .then((s) => setIndicePronto(s.indice_pronto))
      .catch(() => setIndicePronto(false))
  }, [])

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
      const resposta = await chatPesquisa(pergunta)
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
            ? {
                ...m,
                texto:
                  'Não foi possível consultar o guia. Verifique se o backend está ativo e se o índice FAISS foi gerado (scripts/build_faiss_index.py).',
                carregando: false,
              }
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
      {indicePronto === false && (
        <div className="mx-4 mt-3 px-3 py-2 bg-amber-950/50 border border-amber-800 rounded-lg text-xs text-amber-200 flex items-center gap-2">
          <BookOpen size={14} />
          Índice FAISS ainda em construção. Aguarde alguns segundos e tente novamente.
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite">
        {mensagens.map((msg) => (
          <div
            key={msg.id}
            className={clsx('flex gap-3', msg.tipo === 'agente' ? 'items-start' : 'items-start flex-row-reverse')}
          >
            <div
              className={clsx(
                'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                msg.tipo === 'agente' ? 'bg-indigo-600' : 'bg-gray-700',
              )}
            >
              {msg.tipo === 'agente' ? (
                <BookOpen size={16} className="text-white" />
              ) : (
                <User size={16} className="text-gray-300" />
              )}
            </div>
            <div className="max-w-[85%] space-y-2">
              <div
                className={clsx(
                  'rounded-2xl px-4 py-3 text-sm leading-relaxed',
                  msg.tipo === 'agente' ? 'bg-gray-800 text-gray-200' : 'bg-indigo-600 text-white',
                )}
              >
                {msg.carregando ? (
                  <div className="flex items-center gap-2 text-gray-400">
                    <Loader2 size={14} className="animate-spin" />
                    <span>Consultando documentação (FAISS)...</span>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.texto}</p>
                )}
              </div>
              {msg.resposta && msg.resposta.fontes.length > 0 && (
                <div className="flex flex-wrap gap-1 items-center text-xs text-gray-500">
                  <FileText size={11} />
                  {msg.resposta.fontes.map((f) => (
                    <span key={f} className="bg-gray-900 border border-gray-800 px-2 py-0.5 rounded-full">
                      {f}
                    </span>
                  ))}
                  <span className="text-gray-600">· {msg.resposta.fragmentos_usados} trechos</span>
                </div>
              )}
              <time className="text-xs text-gray-600 block">
                {format(msg.timestamp, 'HH:mm', { locale: ptBR })}
              </time>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 pb-2 flex gap-2 overflow-x-auto scrollbar-hide">
        {SUGESTOES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => enviar(s)}
            disabled={enviando}
            className="shrink-0 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-full transition-colors disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pergunte sobre a pesquisa, arquitetura ou como usar o sistema..."
            rows={2}
            disabled={enviando}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:border-indigo-500 disabled:opacity-50"
            aria-label="Pergunta sobre a aplicação"
          />
          <button
            type="button"
            onClick={() => enviar(input)}
            disabled={!input.trim() || enviando}
            className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white rounded-xl transition-colors"
            aria-label="Enviar"
          >
            {enviando ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-1.5 flex items-center gap-1">
          <Bot size={11} /> RAG FAISS + DeepSeek · base: backend/knowledge/
        </p>
      </div>
    </div>
  )
}
