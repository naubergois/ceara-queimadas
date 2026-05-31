"""
Endpoints FastAPI para dados REAIS de queimadas.
Sem banco de dados — consulta diretamente NASA FIRMS e Open-Meteo.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.agents.explicador_agent import explicar_foco, _explicar_sem_llm
from app.agents.llm_factory import get_deepseek_model, llm_is_configured
from app.core.config import settings
from app.services.clima_real import buscar_clima_municipios_ceara, buscar_clima_foco
from app.services.firms_real import coletar_focos_firms_real
from app.services.geocoder import geocodificar_lote

router = APIRouter(prefix="/real", tags=["Dados Reais"])
logger = logging.getLogger(__name__)

# Cache em memória para evitar re-coleta a cada request
_cache_focos: list[dict] = []
_cache_clima: list[dict] = []
_cache_ts: Optional[datetime] = None
_geocode_task: Optional[asyncio.Task] = None
CACHE_TTL_SEGUNDOS = 300  # 5 minutos
# Nominatim ~1 req/s — geocodificar todos os focos bloqueia a primeira resposta por minutos
MAX_GEOCODE_FOCOS = 40


async def _geocodificar_em_background(focos: list[dict]) -> None:
    """Completa municípios no cache sem bloquear a primeira resposta HTTP."""
    global _cache_focos
    try:
        focos_geo = await geocodificar_lote(focos, max_concorrente=3)
        _cache_focos = focos_geo
        logger.info("Geocoding em background concluído: %d focos", len(focos_geo))
    except Exception as e:
        logger.warning("Geocoding em background falhou: %s", e)


async def _garantir_cache(dias: int = 7):
    """Atualiza o cache se estiver vazio ou expirado."""
    global _cache_focos, _cache_clima, _cache_ts, _geocode_task

    agora = datetime.utcnow()
    if _cache_ts and (agora - _cache_ts).total_seconds() < CACHE_TTL_SEGUNDOS and _cache_focos:
        return

    logger.info("Atualizando cache de focos reais...")

    # Coleta focos e clima em paralelo
    focos_raw, clima = await asyncio.gather(
        coletar_focos_firms_real(dias=dias),
        buscar_clima_municipios_ceara(),
    )

    # Resposta rápida: geocodifica só uma amostra; o restante roda em background
    amostra = focos_raw[:MAX_GEOCODE_FOCOS]
    restante = focos_raw[MAX_GEOCODE_FOCOS:]
    focos_geo = await geocodificar_lote(amostra, max_concorrente=3)

    _cache_focos = focos_geo + restante
    _cache_clima = clima
    _cache_ts = agora
    logger.info(
        "Cache atualizado: %d focos (%d geocodificados), %d municípios com clima",
        len(_cache_focos),
        len(focos_geo),
        len(clima),
    )

    if restante and (_geocode_task is None or _geocode_task.done()):
        _geocode_task = asyncio.create_task(_geocodificar_em_background(_cache_focos))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/focos", summary="Focos reais NASA FIRMS no Ceará")
async def get_focos_reais(
    dias: int = Query(default=7, ge=1, le=7, description="Janela de tempo em dias (máx 7)"),
    severidade: Optional[str] = Query(default=None, description="baixa/media/alta/critica"),
    fonte: Optional[str] = Query(default=None, description="NASA_FIRMS"),
):
    """
    Retorna focos de queimada REAIS coletados do NASA FIRMS para o Ceará.
    Dados NRT (Near Real Time) — sem banco de dados, direto da fonte.
    """
    await _garantir_cache(dias)
    focos = _cache_focos

    if severidade:
        focos = [f for f in focos if f.get("severidade") == severidade]

    return {
        "total": len(focos),
        "fonte": "NASA FIRMS (VIIRS SNPP + NOAA-20 + MODIS)",
        "periodo_dias": dias,
        "atualizado_em": _cache_ts.isoformat() if _cache_ts else None,
        "focos": focos,
    }


@router.get("/clima", summary="Dados climáticos reais dos municípios do Ceará")
async def get_clima_real():
    """
    Retorna dados climáticos REAIS dos principais municípios do Ceará.
    Fonte: Open-Meteo API (gratuita, sem chave).
    """
    await _garantir_cache()
    return {
        "total": len(_cache_clima),
        "fonte": "Open-Meteo API",
        "municipios": _cache_clima,
    }


@router.get("/focos/{foco_id}/explicacao", summary="Explicação do agente para um foco real")
async def get_explicacao_foco(foco_id: str):
    """
    Usa o agente ReAct para explicar por que um foco específico foi detectado.
    Consulta dados climáticos reais e analisa intensidade.
    """
    await _garantir_cache()

    foco = next((f for f in _cache_focos if f["id"] == foco_id), None)
    if not foco:
        raise HTTPException(
            status_code=404,
            detail="Foco não encontrado. Atualize a lista de focos e tente novamente.",
        )

    if llm_is_configured():
        try:
            explicacao = await explicar_foco(foco)
        except Exception as e:
            logger.warning("Agente DeepSeek falhou, usando fallback: %s", e)
            explicacao = await _explicar_sem_llm(foco)
    else:
        explicacao = await _explicar_sem_llm(foco)

    return {**foco, "analise_agente": explicacao}


@router.post("/focos/explicar-lote", summary="Explica múltiplos focos em lote")
async def explicar_focos_lote(payload: dict):
    """
    Explica múltiplos focos. Recebe lista de IDs.
    Útil para o frontend pré-carregar explicações dos focos mais críticos.
    """
    ids = payload.get("ids", [])
    if not ids or len(ids) > 10:
        raise HTTPException(status_code=400, detail="Envie entre 1 e 10 IDs de focos")

    await _garantir_cache()

    focos_alvo = [f for f in _cache_focos if f["id"] in ids]
    if not focos_alvo:
        raise HTTPException(status_code=404, detail="Nenhum foco encontrado")

    # Explica em paralelo (máx 3 simultâneos para não sobrecarregar LLM)
    semaforo = asyncio.Semaphore(3)

    async def _explicar_com_semaforo(foco):
        async with semaforo:
            if llm_is_configured():
                try:
                    return await explicar_foco(foco)
                except Exception as e:
                    logger.warning("DeepSeek lote falhou para %s: %s", foco.get("id"), e)
                    return await _explicar_sem_llm(foco)
            return await _explicar_sem_llm(foco)

    explicacoes = await asyncio.gather(*[_explicar_com_semaforo(f) for f in focos_alvo])

    return {
        "total": len(explicacoes),
        "explicacoes": [
            {**foco, "analise_agente": exp}
            for foco, exp in zip(focos_alvo, explicacoes)
        ],
    }


@router.get("/clima/foco", summary="Clima real para coordenada de um foco")
async def get_clima_foco(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """Retorna dados climáticos reais para a coordenada exata de um foco."""
    clima = await buscar_clima_foco(lat, lon)
    if not clima:
        raise HTTPException(status_code=503, detail="Dados climáticos indisponíveis")
    return {"lat": lat, "lon": lon, "clima": clima, "fonte": "Open-Meteo API"}


@router.get("/status", summary="Status das fontes de dados reais")
async def status_fontes():
    """Verifica disponibilidade das fontes de dados reais."""
    import httpx

    resultados = {}

    # Testa NASA FIRMS
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.head(
                "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv"
            )
            resultados["nasa_firms"] = {"status": "ok", "http": r.status_code}
    except Exception as e:
        resultados["nasa_firms"] = {"status": "erro", "detalhe": str(e)}

    # Testa Open-Meteo
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": -5.1, "longitude": -39.3, "current": "temperature_2m"},
            )
            resultados["open_meteo"] = {"status": "ok", "http": r.status_code}
    except Exception as e:
        resultados["open_meteo"] = {"status": "erro", "detalhe": str(e)}

    # Testa Nominatim
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "CearaQueimadas/1.0"}) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": -5.1, "lon": -39.3, "format": "json"},
            )
            resultados["nominatim"] = {"status": "ok", "http": r.status_code}
    except Exception as e:
        resultados["nominatim"] = {"status": "erro", "detalhe": str(e)}

    resultados["deepseek_configurado"] = llm_is_configured()
    resultados["deepseek_model"] = get_deepseek_model() if llm_is_configured() else None
    resultados["openai_configurado"] = resultados["deepseek_configurado"]  # compat. frontend antigo
    resultados["cache_focos"] = len(_cache_focos)
    resultados["cache_atualizado"] = _cache_ts.isoformat() if _cache_ts else None

    return resultados
