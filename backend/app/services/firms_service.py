"""
Serviço de coleta de focos via NASA FIRMS (MODIS/VIIRS).
"""

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import FocoQueimada

logger = logging.getLogger(__name__)

# Bounding box Ceará: W,S,E,N
CEARA_BBOX = f"{settings.CEARA_LON_MIN},{settings.CEARA_LAT_MIN},{settings.CEARA_LON_MAX},{settings.CEARA_LAT_MAX}"


async def coletar_focos_firms(
    dias: int = 1,
    sensor: str = "VIIRS_SNPP_NRT",
) -> list[FocoQueimada]:
    """
    Coleta focos do NASA FIRMS para o bounding box do Ceará.
    sensor: MODIS_NRT | VIIRS_SNPP_NRT | VIIRS_NOAA20_NRT
    """
    url = f"{settings.NASA_FIRMS_URL}/{sensor}/{CEARA_BBOX}/{dias}"
    params = {"MAP_KEY": settings.NASA_FIRMS_API_KEY}

    focos: list[FocoQueimada] = []

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            content = response.text

        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            try:
                lat = float(row.get("latitude", 0))
                lon = float(row.get("longitude", 0))
                acq_date = row.get("acq_date", "")
                acq_time = row.get("acq_time", "0000").zfill(4)
                data_hora = datetime.strptime(
                    f"{acq_date} {acq_time[:2]}:{acq_time[2:]}", "%Y-%m-%d %H:%M"
                )

                foco = FocoQueimada(
                    fonte="NASA_FIRMS",
                    latitude=lat,
                    longitude=lon,
                    data_hora=data_hora,
                    satelite=row.get("satellite", sensor),
                    sensor=sensor,
                    confianca=_confianca_firms(row.get("confidence", "")),
                    temperatura_k=_safe_float(row.get("bright_t31") or row.get("bright_ti4")),
                    frp=_safe_float(row.get("frp")),
                )
                focos.append(foco)
            except (ValidationError, ValueError) as e:
                logger.warning("Foco FIRMS inválido: %s | %s", row, e)

    except httpx.HTTPError as e:
        logger.error("Erro ao consultar NASA FIRMS: %s", e)
        return []

    logger.info("NASA FIRMS (%s): %d focos coletados", sensor, len(focos))
    return focos


def _confianca_firms(valor: str) -> Optional[float]:
    """Converte confiança FIRMS (n/l/h ou 0-100) para float 0-100."""
    mapa = {"n": 30.0, "l": 30.0, "h": 80.0, "nominal": 60.0}
    if valor.lower() in mapa:
        return mapa[valor.lower()]
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def _safe_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
