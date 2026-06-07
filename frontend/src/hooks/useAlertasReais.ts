/**
 * Hook para alertas gerados a partir de focos NASA FIRMS + clima Open-Meteo.
 */

import { useCallback, useEffect } from 'react'
import { getAlertasReais } from '../services/api'
import { useQueimadasStore } from '../store/useQueimadasStore'

const INTERVALO_MS = 10 * 60 * 1000

export function useAlertasReais() {
  const {
    diasFocosReais,
    alertas,
    carregandoAlertas,
    erroAlertas,
    setAlertas,
    setCarregandoAlertas,
    setErroAlertas,
  } = useQueimadasStore()

  const carregar = useCallback(async () => {
    setCarregandoAlertas(true)
    setErroAlertas(null)
    try {
      const lista = await getAlertasReais(diasFocosReais, 48)
      setAlertas(lista)
    } catch {
      setErroAlertas('Não foi possível carregar os alertas. Aguarde os focos reais e tente novamente.')
      setAlertas([])
    } finally {
      setCarregandoAlertas(false)
    }
  }, [diasFocosReais, setAlertas, setCarregandoAlertas, setErroAlertas])

  useEffect(() => {
    carregar()
    const timer = setInterval(carregar, INTERVALO_MS)
    return () => clearInterval(timer)
  }, [carregar])

  return {
    alertas,
    carregando: carregandoAlertas,
    erro: erroAlertas,
    recarregar: carregar,
  }
}
