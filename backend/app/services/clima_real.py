"""
Dados climáticos REAIS via Open-Meteo API (gratuita, sem chave).
Busca temperatura, umidade, vento e precipitação para qualquer coordenada.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Municípios representativos do Ceará com coordenadas
MUNICIPIOS_CEARA = [
    {"nome": "Fortaleza",        "lat": -3.7172,  "lon": -38.5433},
    {"nome": "Juazeiro do Norte","lat": -7.2136,  "lon": -39.3153},
    {"nome": "Sobral",           "lat": -3.6861,  "lon": -40.3497},
    {"nome": "Crato",            "lat": -7.2342,  "lon": -39.4095},
    {"nome": "Maracanaú",        "lat": -3.8769,  "lon": -38.6258},
    {"nome": "Caucaia",          "lat": -3.7361,  "lon": -38.6531},
    {"nome": "Quixadá",          "lat": -4.9711,  "lon": -39.0153},
    {"nome": "Iguatu",           "lat": -6.3594,  "lon": -39.2986},
    {"nome": "Crateús",          "lat": -5.1769,  "lon": -40.6681},
    {"nome": "Tianguá",          "lat": -3.7328,  "lon": -40.9914},
    {"nome": "Limoeiro do Norte","lat": -5.1453,  "lon": -38.0997},
    {"nome": "Russas",           "lat": -4.9408,  "lon": -37.9742},
    {"nome": "Aracati",          "lat": -4.5614,  "lon": -37.7697},
    {"nome": "Itapipoca",        "lat": -3.4942,  "lon": -39.5786},
    {"nome": "Canindé",          "lat": -4.3567,  "lon": -39.3139},
    {"nome": "Tauá",             "lat": -5.9836,  "lon": -40.2928},
    {"nome": "Brejo Santo",      "lat": -7.4908,  "lon": -38.9847},
    {"nome": "Icó",              "lat": -6.4011,  "lon": -38.8614},
    {"nome": "Senador Pompeu",   "lat": -5.5819,  "lon": -39.3706},
    {"nome": "Jaguaribe",        "lat": -5.8908,  "lon": -38.6228},
]


async def buscar_clima_por_coordenada(lat: float, lon: float) -> dict:
    """
    Busca dados climáticos atuais para uma coordenada via Open-Meteo.
    Retorna dict com temperatura, umidade, vento e precipitação.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code",
        "daily": "precipitation_sum",
        "past_days": 14,
        "timezone": "America/Fortaleza",
        "forecast_days": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        daily = data.get("daily", {})

        # Calcular dias sem chuva
        precip_diaria = daily.get("precipitation_sum", [])
        dias_sem_chuva = 0
        for p in reversed(precip_diaria):
            if p is not None and p > 0.1:
                break
            dias_sem_chuva += 1

        return {
            "temperatura_c": current.get("temperature_2m"),
            "umidade_relativa": current.get("relative_humidity_2m"),
            "velocidade_vento_ms": round((current.get("wind_speed_10m") or 0) / 3.6, 2),  # km/h → m/s
            "direcao_vento_graus": current.get("wind_direction_10m"),
            "precipitacao_mm": current.get("precipitation"),
            "dias_sem_chuva": dias_sem_chuva,
            "weather_code": current.get("weather_code"),
        }
    except Exception as e:
        logger.warning("Erro Open-Meteo (%.4f, %.4f): %s", lat, lon, e)
        return {}


async def buscar_clima_municipios_ceara() -> list[dict]:
    """
    Busca dados climáticos reais para os principais municípios do Ceará.
    Retorna lista de dicts com nome, coordenadas e dados climáticos.
    """
    import asyncio

    async def _buscar(mun: dict) -> dict:
        clima = await buscar_clima_por_coordenada(mun["lat"], mun["lon"])
        return {**mun, **clima}

    # Busca em paralelo (máx 5 simultâneos para não sobrecarregar)
    semaforo = asyncio.Semaphore(5)

    async def _com_semaforo(mun):
        async with semaforo:
            return await _buscar(mun)

    resultados = await asyncio.gather(*[_com_semaforo(m) for m in MUNICIPIOS_CEARA])
    logger.info("Clima real: %d municípios consultados", len(resultados))
    return list(resultados)


async def buscar_clima_foco(lat: float, lon: float) -> dict:
    """Busca clima real para a coordenada exata de um foco."""
    return await buscar_clima_por_coordenada(lat, lon)
