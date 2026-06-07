/**
 * StatusFontes — barra de status das fontes de dados reais.
 */

import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Loader2, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import { getStatusFontes, type StatusFontes } from '../services/api'

export default function StatusFontes() {
  const [status, setStatus] = useState<StatusFontes | null>(null)
  const [carregando, setCarregando] = useState(true)

  const verificar = () => {
    setCarregando(true)
    getStatusFontes()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setCarregando(false))
  }

  useEffect(() => { verificar() }, [])

  const fontes = status ? [
    { nome: 'NASA FIRMS', ok: status.nasa_firms?.status === 'ok' },
    { nome: 'Open-Meteo', ok: status.open_meteo?.status === 'ok' },
    { nome: 'Nominatim', ok: status.nominatim?.status === 'ok' },
    {
      nome: status.deepseek_model ? `DeepSeek` : 'DeepSeek',
      ok: status.deepseek_configurado ?? status.openai_configurado,
    },
  ] : []

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs shadow-sm">
      {carregando ? (
        <Loader2 size={12} className="animate-spin text-slate-400" />
      ) : (
        <>
          {fontes.map(({ nome, ok }) => (
            <div key={nome} className="flex items-center gap-1">
              {ok ? (
                <CheckCircle size={12} className="text-emerald-600" />
              ) : (
                <XCircle size={12} className="text-red-500" />
              )}
              <span className={clsx('hidden sm:inline font-medium', ok ? 'text-slate-600' : 'text-red-600')}>
                {nome}
              </span>
            </div>
          ))}
          {status && (
            <span className="text-slate-400 hidden md:inline border-l border-slate-200 pl-3">
              {status.cache_focos} focos
            </span>
          )}
        </>
      )}
      <button
        type="button"
        onClick={verificar}
        className="ml-auto p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-white transition-colors"
        aria-label="Verificar status das fontes"
      >
        <RefreshCw size={12} className={carregando ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}
