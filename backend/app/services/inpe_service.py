"""
Serviço de coleta de focos de queimada do INPE BDQueimadas.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import FocoQueimada

logger = logging.getLogger(__name__)

INPE_BASE_URL = settings.INPE_API_URL


async def coletar_focos_inpe(
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    estado: str = "CE",
) -> list[FocoQueimada]:
    """
    Coleta focos de queimada do INPE BDQueimadas para o Ceará.
    Retorna lista de FocoQueimada validados com Pydantic.
    """
    if data_inicio is None:
        data_inicio = datetime.utcnow() - timedelta(hours=24)
    if data_fim is None:
        data_fim = datetime.utcnow()

    params = {
        "estado": estado,
        "data_inicio": data_inicio.strftime("%Y-%m-%d"),
        "data_fim": data_fim.strftime("%Y-%m-%d"),
        "formato": "json",
    }
    if settings.INPE_API_KEY:
        params["token"] = settings.INPE_API_KEY

    focos: list[FocoQueimada] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{INPE_BASE_URL}/focos", params=params)
            response.raise_for_status()
            dados = response.json()

        for item in dados.get("focos", dados if isinstance(dados, list) else []):
            try:
                foco = FocoQueimada(
                    fonte="INPE",
                    latitude=float(item.get("latitude", item.get("lat", 0))),
                    longitude=float(item.get("longitude", item.get("lon", 0))),
                    data_hora=_parse_datetime(item.get("data_hora", item.get("datahora", ""))),
                    municipio=item.get("municipio"),
                    bioma=item.get("bioma"),
                    satelite=item.get("satelite"),
                    sensor=item.get("sensor"),
                    confianca=_safe_float(item.get("confianca")),
                    frp=_safe_float(item.get("frp")),
                )
                focos.append(foco)
            except (ValidationError, ValueError) as e:
                logger.warning("Foco INPE inválido ignorado: %s | erro: %s", item, e)

    except httpx.HTTPError as e:
        logger.error("Erro ao consultar INPE: %s", e)
        # Tolerância a falhas: retorna lista vazia sem lançar exceção
        return []

    logger.info("INPE: %d focos coletados para %s", len(focos), estado)
    return focos


def _parse_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


def _safe_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
