/**
 * Hook para focos reais NASA FIRMS — mesma fonte do Mapa Real.
 */

import { useCallback, useEffect } from 'react'
import { getFocosReais } from '../services/api'
import { useQueimadasStore } from '../store/useQueimadasStore'

const INTERVALO_MS = 10 * 60 * 1000 // 10 min (coleta FIRMS é pesada)

export function useFocosReais() {
  const {
    diasFocosReais,
    focosReais,
    atualizadoEmReais,
    carregandoReais,
    erroReais,
    setFocosReais,
    setAtualizadoEmReais,
    setCarregandoReais,
    setErroReais,
    setDiasFocosReais,
  } = useQueimadasStore()

  const carregar = useCallback(async () => {
    setCarregandoReais(true)
    setErroReais(null)
    try {
      const resp = await getFocosReais(diasFocosReais)
      setFocosReais(resp.focos)
      setAtualizadoEmReais(resp.atualizado_em)
    } catch (e) {
      const msg =
        e instanceof Error && e.message.includes('timeout')
          ? 'The first load of real data may take up to 2 minutes. Try refreshing again.'
          : 'Could not load real hotspots (NASA FIRMS). Check the backend.'
      setErroReais(msg)
    } finally {
      setCarregandoReais(false)
    }
  }, [
    diasFocosReais,
    setFocosReais,
    setAtualizadoEmReais,
    setCarregandoReais,
    setErroReais,
  ])

  useEffect(() => {
    carregar()
    const timer = setInterval(carregar, INTERVALO_MS)
    return () => clearInterval(timer)
  }, [carregar])

  return {
    focos: focosReais,
    atualizadoEm: atualizadoEmReais,
    dias: diasFocosReais,
    setDias: setDiasFocosReais,
    carregando: carregandoReais,
    erro: erroReais,
    recarregar: carregar,
  }
}
