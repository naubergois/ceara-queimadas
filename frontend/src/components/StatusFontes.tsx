/**
 * StatusFontes — barra de status das fontes de dados reais.
 * Mostra se NASA FIRMS, Open-Meteo, Nominatim e DeepSeek estão disponíveis.
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
      nome: status.deepseek_model ? `DeepSeek (${status.deepseek_model})` : 'DeepSeek',
      ok: status.deepseek_configurado ?? status.openai_configurado,
    },
  ] : []

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 bg-gray-900 border border-gray-800 rounded-lg text-xs">
      {carregando ? (
        <Loader2 size={12} className="animate-spin text-gray-500" />
      ) : (
        <>
          {fontes.map(({ nome, ok }) => (
            <div key={nome} className="flex items-center gap-1">
              {ok
                ? <CheckCircle size={11} className="text-green-400" />
                : <XCircle size={11} className="text-red-400" />
              }
              <span className={clsx('hidden sm:inline', ok ? 'text-gray-400' : 'text-red-400')}>
                {nome}
              </span>
            </div>
          ))}
          {status && (
            <span className="text-gray-600 hidden md:inline">
              {status.cache_focos} focos em cache
            </span>
          )}
        </>
      )}
      <button
        onClick={verificar}
        className="ml-auto text-gray-600 hover:text-gray-400 transition-colors"
        aria-label="Verificar status das fontes"
      >
        <RefreshCw size={11} className={carregando ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}
