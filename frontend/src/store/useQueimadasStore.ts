/**
 * Store global com Zustand para estado da plataforma de queimadas.
 */

import { create } from 'zustand'
import type { Alerta, CamadaMapa, Foco, LeituraGOES16, RiscoMunicipal } from '../services/api'

interface QueimadasState {
  // Dados
  focos: Foco[]
  riscos: RiscoMunicipal[]
  alertas: Alerta[]
  leituraGOES16: LeituraGOES16[]
  camadas: CamadaMapa[]

  // Filtros
  filtroHoras: number
  filtroFonte: string | null
  filtroSeveridade: string | null
  filtroMunicipio: string | null

  // UI
  carregando: boolean
  erro: string | null
  eventoSelecionado: string | null

  // Actions
  setFocos: (focos: Foco[]) => void
  setRiscos: (riscos: RiscoMunicipal[]) => void
  setAlertas: (alertas: Alerta[]) => void
  setLeituraGOES16: (leituras: LeituraGOES16[]) => void
  setCamadas: (camadas: CamadaMapa[]) => void
  toggleCamada: (id: string) => void
  setFiltroHoras: (horas: number) => void
  setFiltroFonte: (fonte: string | null) => void
  setFiltroSeveridade: (sev: string | null) => void
  setFiltroMunicipio: (mun: string | null) => void
  setCarregando: (v: boolean) => void
  setErro: (e: string | null) => void
  setEventoSelecionado: (id: string | null) => void
}

export const useQueimadasStore = create<QueimadasState>((set) => ({
  focos: [],
  riscos: [],
  alertas: [],
  leituraGOES16: [],
  camadas: [],

  filtroHoras: 24,
  filtroFonte: null,
  filtroSeveridade: null,
  filtroMunicipio: null,

  carregando: false,
  erro: null,
  eventoSelecionado: null,

  setFocos: (focos) => set({ focos }),
  setRiscos: (riscos) => set({ riscos }),
  setAlertas: (alertas) => set({ alertas }),
  setLeituraGOES16: (leituraGOES16) => set({ leituraGOES16 }),
  setCamadas: (camadas) => set({ camadas }),
  toggleCamada: (id) =>
    set((state) => ({
      camadas: state.camadas.map((c) => (c.id === id ? { ...c, ativo: !c.ativo } : c)),
    })),
  setFiltroHoras: (filtroHoras) => set({ filtroHoras }),
  setFiltroFonte: (filtroFonte) => set({ filtroFonte }),
  setFiltroSeveridade: (filtroSeveridade) => set({ filtroSeveridade }),
  setFiltroMunicipio: (filtroMunicipio) => set({ filtroMunicipio }),
  setCarregando: (carregando) => set({ carregando }),
  setErro: (erro) => set({ erro }),
  setEventoSelecionado: (eventoSelecionado) => set({ eventoSelecionado }),
}))
