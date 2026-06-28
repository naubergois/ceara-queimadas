/**
 * DialogoGuiaPesquisa — botão flutuante com mascote + modal do chat RAG (FAISS).
 */

import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { clsx } from 'clsx'
import ChatPesquisa from './ChatPesquisa'
import MascoteGuia, { NOME_MASCOTE } from './MascoteGuia'

const STORAGE_KEY = 'guia-ioio-visto'

interface Props {
  aberto: boolean
  onFechar: () => void
  onAbrir: () => void
}

export default function DialogoGuiaPesquisa({ aberto, onFechar, onAbrir }: Props) {
  const [destacar, setDestacar] = useState(false)

  useEffect(() => {
    try {
      setDestacar(!localStorage.getItem(STORAGE_KEY))
    } catch {
      setDestacar(true)
    }
  }, [])

  const abrir = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1')
    } catch {
      /* ignore */
    }
    setDestacar(false)
    onAbrir()
  }

  useEffect(() => {
    if (!aberto) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [aberto, onFechar])

  return (
    <>
      {!aberto && (
        <div className="fixed bottom-5 right-4 sm:right-6 z-40 flex flex-col items-end gap-2 pointer-events-none">
          {/* Balão de fala */}
          <div
            className={clsx(
              'pointer-events-none relative max-w-[220px] sm:max-w-none',
              'bg-white border-2 border-violet-200 text-slate-800',
              'px-3.5 py-2 rounded-2xl rounded-br-md shadow-soft text-sm font-medium',
              destacar && 'animate-mascote-float',
            )}
            aria-hidden
          >
            <span className="text-violet-700 font-semibold">{NOME_MASCOTE}</span>
            <span className="text-slate-600"> — your Ceará research guide!</span>
            <span
              className="absolute -bottom-2 right-6 w-4 h-4 bg-white border-r-2 border-b-2 border-violet-200 rotate-45"
              aria-hidden
            />
          </div>

          <button
            type="button"
            onClick={abrir}
            className={clsx(
              'pointer-events-auto relative flex items-center gap-3',
              'bg-gradient-to-r from-violet-600 via-violet-600 to-fire-600',
              'hover:from-violet-700 hover:via-violet-700 hover:to-fire-700',
              'text-white pl-2 pr-5 py-2.5 rounded-full shadow-guia',
              'transition-all hover:scale-[1.03] active:scale-[0.98]',
              'ring-4 ring-violet-300/50',
              destacar && 'animate-guia-pulse ring-violet-400/60',
            )}
            aria-label={`Open guide with ${NOME_MASCOTE} — ask about the research`}
          >
            {destacar && (
              <span
                className="absolute inset-0 rounded-full bg-violet-400 animate-ping opacity-30"
                aria-hidden
              />
            )}
            <span className="relative flex shrink-0 rounded-full bg-white/20 p-0.5">
              <MascoteGuia size={48} animado ariaHidden />
            </span>
            <span className="flex flex-col items-start text-left pr-1">
              <span className="text-sm font-bold leading-tight">{NOME_MASCOTE}</span>
              <span className="text-[11px] font-medium text-white/90 leading-tight">
                Ceará guide
              </span>
            </span>
          </button>
        </div>
      )}

      {aberto && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="dialogo-guia-titulo"
        >
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
            onClick={onFechar}
            aria-label="Close dialog"
          />

          <div
            className={clsx(
              'relative z-10 flex flex-col w-full sm:max-w-lg',
              'bg-white border-2 border-violet-200',
              'rounded-t-3xl sm:rounded-3xl shadow-panel',
              'h-[min(88vh,760px)] sm:h-[min(82vh,720px)]',
            )}
          >
            <header className="flex items-center justify-between px-5 py-4 border-b border-violet-100 shrink-0 bg-gradient-to-r from-violet-100 via-orange-50 to-white rounded-t-3xl sm:rounded-t-3xl">
              <div className="flex items-center gap-3 min-w-0">
                <div className="relative shrink-0">
                  <MascoteGuia size={52} animado />
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full" title="Online" />
                </div>
                <div className="min-w-0">
                  <h2 id="dialogo-guia-titulo" className="text-base font-bold text-slate-900 truncate">
                    {NOME_MASCOTE} — Application guide
                  </h2>
                  <p className="text-xs text-violet-700 font-medium truncate">
                    The map of Ceará that explains the research
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onFechar}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-white/80 transition-colors shrink-0"
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </header>

            <div className="flex-1 min-h-0 overflow-hidden bg-gradient-to-b from-violet-50/40 to-slate-50/80">
              <ChatPesquisa />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
