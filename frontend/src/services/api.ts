/**
 * Serviço de comunicação com a API backend FastAPI.
 */

import axios from 'axios'

/** Em dev o Vite faz proxy de /api → backend; em produção o nginx faz o mesmo. */
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

/** Coleta NASA FIRMS + geocoding pode levar 1–2 min na primeira requisição. */
export const apiReal = axios.create({
  baseURL: BASE_URL,
  timeout: 180_000,
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

// ---------------------------------------------------------------------------
// Dados REAIS (sem banco — direto das fontes NASA FIRMS + Open-Meteo)
// ---------------------------------------------------------------------------

export interface FocoReal {
  id: string
  fonte: string
  satelite: string
  sensor: string
  lat: number
  lon: number
  latitude: number
  longitude: number
  data_hora: string
  municipio: string | null
  confianca: number
  frp: number | null
  temperatura_k: number | null
  severidade: 'baixa' | 'media' | 'alta' | 'critica'
  daynight: string
  scan: number | null
  track: number | null
}

export interface ClimaReal {
  nome?: string
  lat?: number
  lon?: number
  temperatura_c: number | null
  umidade_relativa: number | null
  velocidade_vento_ms: number | null
  direcao_vento_graus: number | null
  precipitacao_mm: number | null
  dias_sem_chuva: number
  weather_code: number | null
}

export interface ExplicacaoAgente {
  foco_id: string
  explicacao: string
  clima: Partial<ClimaReal>
  ferramentas_usadas: string[]
  evidencias: string[]
  passos_raciocinio: string[]
  nivel_confianca: number
  gerado_em: string
}

export interface FocoComExplicacao extends FocoReal {
  analise_agente: ExplicacaoAgente
}

export interface StatusFontes {
  nasa_firms: { status: string; http?: number }
  open_meteo: { status: string; http?: number }
  nominatim: { status: string; http?: number }
  deepseek_configurado: boolean
  deepseek_model?: string | null
  /** @deprecated use deepseek_configurado */
  openai_configurado: boolean
  cache_focos: number
  cache_atualizado: string | null
}

export const getFocosReais = (dias = 7, severidade?: string) =>
  apiReal.get<{ total: number; focos: FocoReal[]; atualizado_em: string | null }>(
    '/real/focos',
    { params: { dias, severidade } }
  ).then(r => r.data)

export const getClimaReal = () =>
  apiReal.get<{ municipios: ClimaReal[] }>('/real/clima').then(r => r.data)

export const getExplicacaoFoco = (focoId: string) =>
  apiReal.get<FocoComExplicacao>(`/real/focos/${focoId}/explicacao`).then(r => r.data)

export const explicarFocosLote = (ids: string[]) =>
  apiReal.post<{ total: number; explicacoes: FocoComExplicacao[] }>(
    '/real/focos/explicar-lote',
    { ids }
  ).then(r => r.data)

export const getClimaFoco = (lat: number, lon: number) =>
  apiReal.get<{ clima: ClimaReal }>('/real/clima/foco', { params: { lat, lon } }).then(r => r.data)

export const getStatusFontes = () =>
  apiReal.get<StatusFontes>('/real/status').then(r => r.data)
