/**
 * Componente CardAlerta — exibe um alerta de queimada com nível, município e recomendação.
 */

import { AlertTriangle, CheckCircle, Info, Zap } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import type { Alerta } from '../services/api'

interface Props {
  alerta: Alerta
}

const nivelConfig = {
  informativo: {
    icon: Info,
    bg: 'bg-blue-950 border-blue-800',
    text: 'text-blue-300',
    badge: 'bg-blue-900 text-blue-200',
    label: 'Informativo',
  },
  atencao: {
    icon: AlertTriangle,
    bg: 'bg-yellow-950 border-yellow-800',
    text: 'text-yellow-300',
    badge: 'bg-yellow-900 text-yellow-200',
    label: 'Atenção',
  },
  alerta: {
    icon: AlertTriangle,
    bg: 'bg-orange-950 border-orange-800',
    text: 'text-orange-300',
    badge: 'bg-orange-900 text-orange-200',
    label: 'Alerta',
  },
  emergencia: {
    icon: Zap,
    bg: 'bg-red-950 border-red-800',
    text: 'text-red-300',
    badge: 'bg-red-900 text-red-200',
    label: 'Emergência',
  },
}

export default function CardAlerta({ alerta }: Props) {
  const config = nivelConfig[alerta.nivel]
  const Icon = config.icon

  return (
    <article
      className={clsx(
        'border rounded-xl p-4 space-y-2 transition-all',
        config.bg,
        alerta.nivel === 'emergencia' && 'animate-pulse',
      )}
      role="alert"
      aria-label={`Alerta ${config.label} em ${alerta.municipio}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon size={18} className={config.text} aria-hidden="true" />
          <span className={clsx('text-sm font-semibold', config.text)}>{alerta.municipio}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', config.badge)}>
            {config.label}
          </span>
          {alerta.auditado && (
            <CheckCircle size={14} className="text-green-400" title="Auditado" aria-label="Alerta auditado" />
          )}
        </div>
      </div>

      {/* Mensagem */}
      <p className="text-sm text-gray-300 leading-relaxed">{alerta.mensagem}</p>

      {/* Recomendação */}
      {alerta.recomendacao && (
        <div className="bg-black/20 rounded-lg p-2">
          <p className="text-xs text-gray-400 font-medium mb-0.5">Recomendação</p>
          <p className="text-xs text-gray-300">{alerta.recomendacao}</p>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500 pt-1">
        <time dateTime={alerta.data_hora}>
          {format(new Date(alerta.data_hora), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
        </time>
        <span>Confiança: {(alerta.nivel_confianca * 100).toFixed(0)}%</span>
      </div>
    </article>
  )
}
