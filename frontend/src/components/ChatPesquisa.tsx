/**
 * ChatPesquisa — chat RAG (FAISS) sobre a pesquisa e o funcionamento da aplicação.
 */

import { useEffect, useRef, useState } from 'react'
import { Send, User, Loader2, FileText } from 'lucide-react'
import MascoteGuia, { NOME_MASCOTE } from './MascoteGuia'
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
  'Qual é o objetivo da pesquisa?',
  'Como funciona a arquitetura?',
  'Quais fontes de dados estão ativas?',
  'Como usar o mapa real?',
  'O que faz o agente DeepSeek?',
  'Como fazer deploy na EC2?',
]

export default function ChatPesquisa() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      id: '0',
      tipo: 'agente',
      texto:
        `Oxente! Eu sou o ${NOME_MASCOTE} — o mapa do Ceará com olhos, seu guia nesta plataforma. Pergunte sobre a pesquisa, arquitetura, NASA FIRMS, agentes de IA ou como usar cada tela do sistema.`,
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
                  'Não foi possível consultar o guia. Verifique se o backend está ativo.',
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
        <div className="mx-4 mt-3 alert-warning flex items-center gap-2">
          <MascoteGuia size={20} className="shrink-0" />
          Índice em construção. Aguarde alguns segundos e tente novamente.
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite">
        {mensagens.map((msg) => (
          <div
            key={msg.id}
            className={clsx(
              'flex gap-3',
              msg.tipo === 'agente' ? 'items-start' : 'items-start flex-row-reverse',
            )}
          >
            <div
              className={clsx(
                'rounded-xl flex items-center justify-center shrink-0 shadow-sm overflow-hidden',
                msg.tipo === 'agente'
                  ? 'w-11 h-14 bg-gradient-to-br from-violet-100 to-orange-50 border border-violet-200'
                  : 'w-9 h-9 bg-fire-100 text-fire-700',
              )}
            >
              {msg.tipo === 'agente' ? (
                <MascoteGuia size={32} />
              ) : (
                <User size={16} />
              )}
            </div>
            <div className={clsx('max-w-[85%] space-y-2', msg.tipo === 'usuario' && 'text-right')}>
              <div
                className={clsx(
                  'rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
                  msg.tipo === 'agente'
                    ? 'bg-white border border-slate-200 text-slate-700'
                    : 'bg-fire-600 text-white',
                )}
              >
                {msg.carregando ? (
                  <div className="flex items-center gap-2 text-slate-500">
                    <Loader2 size={14} className="animate-spin text-violet-500" />
                    <span>Consultando documentação...</span>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.texto}</p>
                )}
              </div>
              {msg.resposta && msg.resposta.fontes.length > 0 && (
                <div className="flex flex-wrap gap-1 items-center justify-end text-xs text-slate-500">
                  <FileText size={11} className="text-violet-500" />
                  {msg.resposta.fontes.map((f) => (
                    <span
                      key={f}
                      className="bg-violet-50 text-violet-700 border border-violet-100 px-2 py-0.5 rounded-full"
                    >
                      {f.replace('.md', '').replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              <time className="text-xs text-slate-400 block">
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
            className="shrink-0 text-xs bg-white border border-slate-200 text-slate-600 hover:border-violet-300 hover:text-violet-700 px-3 py-1.5 rounded-full transition-colors disabled:opacity-50 shadow-sm"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-slate-200 bg-white">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Pergunte ao ${NOME_MASCOTE} sobre a pesquisa ou o sistema...`}
            rows={2}
            disabled={enviando}
            className="input-field flex-1 resize-none"
            aria-label="Pergunta sobre a aplicação"
          />
          <button
            type="button"
            onClick={() => enviar(input)}
            disabled={!input.trim() || enviando}
            className="p-3 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl transition-colors shadow-sm"
            aria-label="Enviar"
          >
            {enviando ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-2 text-center">
          {NOME_MASCOTE} · documentação do projeto · FAISS + DeepSeek
        </p>
      </div>
    </div>
  )
}
