"""
Geocodificação reversa para identificar município do Ceará a partir de lat/lon.
Usa Nominatim (OpenStreetMap) — gratuito, sem chave.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "CearaQueimadas/1.0 (monitoramento-queimadas-ceara)"}

# Cache simples em memória para evitar requisições repetidas
_cache: dict[str, Optional[str]] = {}


async def geocodificar_reverso(lat: float, lon: float) -> Optional[str]:
    """
    Retorna o nome do município para uma coordenada.
    Usa cache para evitar requisições duplicadas.
    """
    chave = f"{lat:.3f}_{lon:.3f}"
    if chave in _cache:
        return _cache[chave]

    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "addressdetails": 1,
                    "zoom": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        address = data.get("address", {})
        municipio = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or address.get("state_district")
        )
        _cache[chave] = municipio
        return municipio

    except Exception as e:
        logger.debug("Geocoder erro (%.3f, %.3f): %s", lat, lon, e)
        _cache[chave] = None
        return None


async def geocodificar_lote(focos: list[dict], max_concorrente: int = 3) -> list[dict]:
    """
    Geocodifica uma lista de focos em paralelo com rate limiting.
    Nominatim permite ~1 req/s — usamos semáforo para respeitar o limite.
    """
    semaforo = asyncio.Semaphore(max_concorrente)

    async def _geocodificar_foco(foco: dict) -> dict:
        if foco.get("municipio"):
            return foco
        async with semaforo:
            municipio = await geocodificar_reverso(foco["lat"], foco["lon"])
            await asyncio.sleep(0.4)  # respeita rate limit Nominatim
            return {**foco, "municipio": municipio}

    resultados = await asyncio.gather(*[_geocodificar_foco(f) for f in focos])
    return list(resultados)
