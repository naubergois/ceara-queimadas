"""
Serviço de coleta de dados climáticos do FUNCEME e INMET.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import DadoClimatico

logger = logging.getLogger(__name__)


async def coletar_clima_funceme(municipio: Optional[str] = None) -> list[DadoClimatico]:
    """Coleta dados climáticos do FUNCEME para municípios do Ceará."""
    dados: list[DadoClimatico] = []
    params: dict = {}
    if municipio:
        params["municipio"] = municipio
    if settings.FUNCEME_API_KEY:
        params["token"] = settings.FUNCEME_API_KEY

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{settings.FUNCEME_API_URL}/clima/atual", params=params
            )
            response.raise_for_status()
            items = response.json()

        for item in items if isinstance(items, list) else items.get("dados", []):
            try:
                dado = DadoClimatico(
                    id=str(uuid4()),
                    municipio=item.get("municipio", municipio or ""),
                    data_hora=_parse_dt(item.get("data_hora", "")),
                    fonte="FUNCEME",
                    temperatura_c=_sf(item.get("temperatura")),
                    umidade_relativa=_sf(item.get("umidade")),
                    velocidade_vento_ms=_sf(item.get("vento_velocidade")),
                    direcao_vento_graus=_sf(item.get("vento_direcao")),
                    precipitacao_mm=_sf(item.get("precipitacao")),
                    dias_sem_chuva=_si(item.get("dias_sem_chuva")),
                )
                dados.append(dado)
            except (ValidationError, ValueError) as e:
                logger.warning("Dado climático FUNCEME inválido: %s", e)

    except httpx.HTTPError as e:
        logger.error("Erro FUNCEME: %s", e)

    return dados


async def coletar_clima_inmet(municipio: Optional[str] = None) -> list[DadoClimatico]:
    """Coleta dados das estações automáticas do INMET."""
    dados: list[DadoClimatico] = []
    headers = {}
    if settings.INMET_TOKEN:
        headers["Authorization"] = f"Bearer {settings.INMET_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            # Estações do Ceará
            resp_estacoes = await client.get(
                f"{settings.INMET_API_URL}/estacoes/T/CE"
            )
            resp_estacoes.raise_for_status()
            estacoes = resp_estacoes.json()

        for estacao in estacoes[:20]:  # limita para não sobrecarregar
            codigo = estacao.get("CD_ESTACAO")
            if not codigo:
                continue
            try:
                async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                    resp = await client.get(
                        f"{settings.INMET_API_URL}/estacao/dados/{codigo}"
                    )
                    resp.raise_for_status()
                    obs = resp.json()

                if obs:
                    ultimo = obs[-1] if isinstance(obs, list) else obs
                    dado = DadoClimatico(
                        id=str(uuid4()),
                        municipio=estacao.get("DC_NOME", ""),
                        data_hora=_parse_dt(
                            f"{ultimo.get('DT_MEDICAO', '')} {ultimo.get('HR_MEDICAO', '0000')[:2]}:00"
                        ),
                        fonte="INMET",
                        temperatura_c=_sf(ultimo.get("TEM_INS")),
                        umidade_relativa=_sf(ultimo.get("UMD_INS")),
                        velocidade_vento_ms=_sf(ultimo.get("VEN_VEL")),
                        direcao_vento_graus=_sf(ultimo.get("VEN_DIR")),
                        precipitacao_mm=_sf(ultimo.get("CHUVA")),
                        pressao_hpa=_sf(ultimo.get("PRE_INS")),
                    )
                    dados.append(dado)
            except Exception as e:
                logger.warning("Erro ao coletar INMET estação %s: %s", codigo, e)

    except httpx.HTTPError as e:
        logger.error("Erro INMET: %s", e)

    return dados


def _parse_dt(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


def _sf(v) -> Optional[float]:
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _si(v) -> Optional[int]:
    try:
        return int(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None
