/**
 * Hook para carregar e atualizar dados de queimadas periodicamente.
 */

import { useCallback, useEffect } from 'react'
import {
  getCamadasMapa,
  getEventosGOES16,
  getFocosTempoReal,
  getRiscoMunicipios,
} from '../services/api'
import { useQueimadasStore } from '../store/useQueimadasStore'

const INTERVALO_MS = 5 * 60 * 1000 // 5 minutos

export function useQueimadas() {
  const {
    filtroHoras,
    filtroFonte,
    setFocos,
    setRiscos,
    setLeituraGOES16,
    setCamadas,
    setCarregando,
    setErro,
  } = useQueimadasStore()

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [focos, riscos, goes16, camadas] = await Promise.allSettled([
        getFocosTempoReal(filtroHoras, filtroFonte ?? undefined),
        getRiscoMunicipios(20),
        getEventosGOES16(6),
        getCamadasMapa(),
      ])

      if (focos.status === 'fulfilled') setFocos(focos.value)
      if (riscos.status === 'fulfilled') setRiscos(riscos.value)
      if (goes16.status === 'fulfilled') setLeituraGOES16(goes16.value)
      if (camadas.status === 'fulfilled') setCamadas(camadas.value)
    } catch (e) {
      setErro('Erro ao carregar dados. Verifique a conexão com o servidor.')
    } finally {
      setCarregando(false)
    }
  }, [filtroHoras, filtroFonte, setFocos, setRiscos, setLeituraGOES16, setCamadas, setCarregando, setErro])

  useEffect(() => {
    carregar()
    const timer = setInterval(carregar, INTERVALO_MS)
    return () => clearInterval(timer)
  }, [carregar])

  return { recarregar: carregar }
}
