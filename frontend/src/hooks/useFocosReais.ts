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
          ? 'A primeira carga dos dados reais pode levar até 2 minutos. Tente atualizar novamente.'
          : 'Não foi possível carregar os focos reais (NASA FIRMS). Verifique o backend.'
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
