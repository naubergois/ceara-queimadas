/**
 * Serviço de comunicação com a API backend FastAPI.
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface Foco {
  id: string
  fonte: 'INPE' | 'NASA_FIRMS' | 'GOES16'
  lat: number
  lon: number
  municipio: string | null
  data_hora: string
  severidade: 'baixa' | 'media' | 'alta' | 'critica' | null
  frp: number | null
  confianca: number | null
  temperatura_k: number | null
}

export interface RiscoMunicipal {
  posicao: number
  municipio: string
  indice_risco: number
  classificacao: 'baixo' | 'moderado' | 'alto' | 'critico'
  focos_24h: number
  focos_7d: number
  dias_sem_chuva: number | null
  umidade_media: number | null
  justificativa: string
}

export interface Alerta {
  id_alerta: string
  nivel: 'informativo' | 'atencao' | 'alerta' | 'emergencia'
  municipio: string
  mensagem: string
  recomendacao: string
  data_hora: string
  nivel_confianca: number
  auditado: boolean
}

export interface LeituraGOES16 {
  id: string
  data_hora: string
  lat: number
  lon: number
  municipio: string | null
  temperatura_k: number | null
  frp_mw: number | null
  persistencia_horas: number | null
  deteccoes_consecutivas: number
}

export interface RespostaAgente {
  pergunta: string
  resposta: string
  resumo: string
  evidencias: string[]
  fontes: string[]
  data_hora_consulta: string
  nivel_confianca: number
  recomendacao_operacional: string
  ferramentas_usadas: string[]
  passos_raciocinio: string[]
}

export interface CamadaMapa {
  id: string
  nome: string
  tipo: 'pontos' | 'poligonos' | 'raster' | 'heatmap'
  ativo: boolean
}

// ---------------------------------------------------------------------------
// Funções de API
// ---------------------------------------------------------------------------

export const getFocosTempoReal = (horas = 6, fonte?: string) =>
  api.get<Foco[]>('/focos/tempo-real', { params: { horas, fonte } }).then(r => r.data)

export const getFocosMunicipio = (municipio: string, horas = 24) =>
  api.get<Foco[]>(`/focos/municipio/${encodeURIComponent(municipio)}`, { params: { horas } }).then(r => r.data)

export const getRiscoMunicipios = (limite = 20) =>
  api.get<RiscoMunicipal[]>('/risco/municipios', { params: { limite } }).then(r => r.data)

export const getAlertasAtivos = (nivel?: string) =>
  api.get<Alerta[]>('/alertas/ativos', { params: { nivel } }).then(r => r.data)

export const getEventosGOES16 = (horas = 6, municipio?: string) =>
  api.get<LeituraGOES16[]>('/goes16/eventos', { params: { horas, municipio } }).then(r => r.data)

export const perguntarAgente = (pergunta: string) =>
  api.post<RespostaAgente>('/agente/pergunta', { pergunta }).then(r => r.data)

export const getCamadasMapa = () =>
  api.get<CamadaMapa[]>('/mapa/camadas').then(r => r.data)

export const getBoletim = (municipio?: string) =>
  api.get<{ boletim: string; total_eventos: number; total_alertas: number }>('/relatorios/boletim', {
    params: { municipio },
  }).then(r => r.data)

export const getDetalheEvento = (eventoId: string) =>
  api.get(`/eventos/${eventoId}`).then(r => r.data)
