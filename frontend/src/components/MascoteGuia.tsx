/**
 * Ioiô — mascote cearense: silhueta do mapa do Ceará com olhos e sorriso.
 * Contorno derivado de limites estaduais (GeoJSON IBGE simplificado).
 */

import { useId } from 'react'
import { clsx } from 'clsx'

/** Apelido cearense do guia (diminutivo carinhoso, típico do Nordeste) */
export const NOME_MASCOTE = 'Ioiô'

/** Silhueta do Ceará — viewBox 0 0 64 80 */
const CEARA_PATH =
  'M 22.54,3.77 L 26.67,6.08 L 30.92,8.47 L 35.9,12.07 L 40.58,15.31 L 44.76,17.75 L 49.27,23.13 L 54.17,27.61 L 59.26,30.66 L 53.61,38.69 L 49.35,45.74 L 46.75,50.92 L 43.03,53.48 L 42.86,56.43 L 41.46,60.65 L 39.96,63.18 L 41.04,67.26 L 42.33,70.81 L 40.27,74.11 L 37.22,76.77 L 32.91,74.12 L 27.98,69.34 L 15.82,67.23 L 17.05,61.7 L 11.01,52.86 L 9.84,42.91 L 9.93,39 L 7.19,35.47 L 6.29,30.35 L 7.13,22.96 L 5.71,19.44 L 3.74,14.44 L 4.37,8.65 L 6.48,4.51 L 12.28,3.96 L 19.49,3.4 L 22.54,3.77 Z'

interface Props {
  size?: number
  className?: string
  animado?: boolean
  ariaHidden?: boolean
}

export default function MascoteGuia({
  size = 56,
  className,
  animado = false,
  ariaHidden = true,
}: Props) {
  const gradId = useId().replace(/:/g, '')
  const height = Math.round(size * (80 / 64))

  return (
    <svg
      width={size}
      height={height}
      viewBox="0 0 64 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={clsx(animado && 'animate-mascote-float', className)}
      role={ariaHidden ? 'presentation' : 'img'}
      aria-hidden={ariaHidden}
      aria-label={ariaHidden ? undefined : `${NOME_MASCOTE}, mascot shaped like the map of Ceará`}
    >
      {/* sombra */}
      <path
        d={CEARA_PATH}
        fill="#0f172a"
        opacity="0.08"
        transform="translate(1.2, 1.5)"
      />
      {/* corpo — mapa do Ceará */}
      <path
        d={CEARA_PATH}
        fill={`url(#${gradId})`}
        stroke="#c2410c"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* brilho litorâneo (norte) */}
      <path
        d="M 12.28,3.96 L 22.54,3.77 L 35.9,12.07 L 40.58,15.31"
        stroke="#fff7ed"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.55"
        fill="none"
      />
      {/* olhos */}
      <ellipse cx="28" cy="38" rx="5" ry="5.5" fill="white" />
      <ellipse cx="40" cy="36" rx="5" ry="5.5" fill="white" />
      <circle cx="29" cy="38.5" r="2.4" fill="#1e293b" />
      <circle cx="41" cy="36.5" r="2.4" fill="#1e293b" />
      <circle cx="29.8" cy="37.5" r="0.9" fill="white" />
      <circle cx="41.8" cy="35.5" r="0.9" fill="white" />
      {/* sobrancelhas leves */}
      <path d="M 23 33 Q 28 30 33 33" stroke="#9a3412" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.7" />
      <path d="M 35 31 Q 40 28 45 31" stroke="#9a3412" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.7" />
      {/* sorriso */}
      <path
        d="M 26 48 Q 32 53 38 48"
        stroke="#1e293b"
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      />
      {/* detalhe verde — sertão / vegetação */}
      <circle cx="14" cy="58" r="3" fill="#22c55e" opacity="0.85" />
      <defs>
        <linearGradient id={gradId} x1="8" y1="4" x2="56" y2="76" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fdba74" />
          <stop offset="0.45" stopColor="#f97316" />
          <stop offset="1" stopColor="#ea580c" />
        </linearGradient>
      </defs>
    </svg>
  )
}
