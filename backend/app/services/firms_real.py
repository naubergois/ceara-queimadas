"""
Coleta REAL de focos via NASA FIRMS (API com chave ou CSV público fallback).

Suporta:
  - API oficial FIRMS (NRT) com MAP_KEY via settings.NASA_FIRMS_API_KEY
  - CSV público sem autenticação como fallback
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional
import hashlib

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Bounding box Ceará
LAT_MIN, LAT_MAX = -7.85, -2.78
LON_MIN, LON_MAX = -41.42, -37.25

# MAP_KEY da NASA FIRMS (via settings — obtida em https://firms.modaps.eosdis.nasa.gov/api/map_key/)
FIRMS_MAP_KEY = settings.NASA_FIRMS_API_KEY

# API FIRMS (requer MAP_KEY) — endpoint NRT (Near Real Time) para área
# Formato: api/area/csv/{key}/{SOURCE}/{area}/{day_range}
# Documentação: https://firms.modaps.eosdis.nasa.gov/api/area/
FIRMS_API_AREA = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{day_range}"

# CSVs públicos NASA FIRMS (fallback, sem chave)
FIRMS_SOURCES = {
    "VIIRS_SNPP_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_24h.csv",
    "VIIRS_SNPP_7d":  "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_7d.csv",
    "VIIRS_NOAA20_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv",
    "VIIRS_NOAA20_7d":  "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_7d.csv",
    "MODIS_24h": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_South_America_24h.csv",
    "MODIS_7d":  "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_South_America_7d.csv",
}

CONFIANCA_MAP = {"nominal": 65.0, "low": 30.0, "high": 90.0, "n": 30.0, "l": 30.0, "h": 90.0}


def _foco_id_estavel(lat: float, lon: float, data_hora: str, sensor: str, satelite: str) -> str:
    """ID determinístico para o mesmo foco entre atualizações de cache."""
    raw = f"{lat:.5f}|{lon:.5f}|{data_hora}|{sensor}|{satelite}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_confianca(v: str) -> float:
    if not v:
        return 60.0
    v = v.strip().lower()
    if v in CONFIANCA_MAP:
        return CONFIANCA_MAP[v]
    try:
        return float(v)
    except ValueError:
        return 60.0


def _parse_dt(acq_date: str, acq_time: str) -> datetime:
    t = acq_time.strip().zfill(4)
    try:
        return datetime.strptime(f"{acq_date} {t[:2]}:{t[2:]}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v and v.strip() else None
    except (ValueError, TypeError):
        return None


def _classificar_severidade(frp: Optional[float], confianca: float) -> str:
    if frp is None:
        return "baixa"
    if frp >= 50 or (frp >= 20 and confianca >= 80):
        return "critica"
    if frp >= 15:
        return "alta"
    if frp >= 5:
        return "media"
    return "baixa"


async def _coletar_focos_via_api(dias: int = 1) -> list[dict]:
    """
    Coleta focos FIRMS via API oficial com MAP_KEY.

    Usa o endpoint /api/area/csv/{key}/{SOURCE}/{area}/{day_range}
    para consultar a bounding box do Ceará com os sensores VIIRS_SNPP, VIIRS_NOAA20 e MODIS.
    """
    area_coords = f"{LON_MIN},{LAT_MIN},{LON_MAX},{LAT_MAX}"
    day_range = min(dias, 7)

    sensors_sources = [
        ("VIIRS", "VIIRS_SNPP_NRT"),
        ("VIIRS", "VIIRS_NOAA20_NRT"),
        ("MODIS", "MODIS_NRT"),
    ]

    todos: list[dict] = []
    vistos: set[str] = set()

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for sensor, source in sensors_sources:
            url = FIRMS_API_AREA.format(
                key=FIRMS_MAP_KEY,
                source=source,
                area=area_coords,
                day_range=day_range,
            )
            try:
                logger.info("Consultando FIRMS API: %s (últimos %d dias)", source, day_range)
                resp = await client.get(url)
                resp.raise_for_status()
                reader = csv.DictReader(io.StringIO(resp.text))

                for row in reader:
                    try:
                        lat = float(row.get("latitude", 0))
                        lon = float(row.get("longitude", 0))
                    except (ValueError, TypeError):
                        continue

                    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                        continue

                    acq_date = row.get("acq_date", "")
                    acq_time = row.get("acq_time", "0000")
                    data_hora = _parse_dt(acq_date, acq_time)

                    chave = f"{lat:.4f}_{lon:.4f}_{acq_date}"
                    if chave in vistos:
                        continue
                    vistos.add(chave)

                    confianca = _parse_confianca(row.get("confidence", ""))
                    frp = _safe_float(row.get("frp"))
                    temp_k = _safe_float(row.get("bright_ti4") or row.get("brightness"))

                    satelite = row.get("satellite", sensor)
                    severidade = _classificar_severidade(frp, confianca)

                    foco = {
                        "id": _foco_id_estavel(lat, lon, data_hora.isoformat(), sensor, satelite),
                        "fonte": "NASA_FIRMS_API",
                        "satelite": satelite,
                        "sensor": sensor,
                        "lat": lat,
                        "lon": lon,
                        "latitude": lat,
                        "longitude": lon,
                        "data_hora": data_hora.isoformat(),
                        "municipio": None,
                        "confianca": confianca,
                        "frp": frp,
                        "temperatura_k": temp_k,
                        "severidade": severidade,
                        "daynight": row.get("daynight", ""),
                        "scan": _safe_float(row.get("scan")),
                        "track": _safe_float(row.get("track")),
                    }
                    todos.append(foco)

                logger.info("FIRMS API %s: %d focos no Ceará", source, len(
                    [f for f in todos if f["sensor"] == sensor]
                ))

            except httpx.HTTPStatusError as e:
                logger.warning("FIRMS API %s: HTTP %s — %s", source, e.response.status_code, e)
            except httpx.HTTPError as e:
                logger.warning("FIRMS API %s: erro de conexão — %s", source, e)
            except Exception as e:
                logger.error("FIRMS API %s: erro inesperado — %s", source, e)

    logger.info("FIRMS API total: %d focos coletados no Ceará", len(todos))
    return todos


async def coletar_focos_firms_real(dias: int = 7) -> list[dict]:
    """
    Coleta focos reais do NASA FIRMS para o Ceará.

    Tenta primeiro a API oficial FIRMS (com MAP_KEY se disponível).
    Se a API falhar ou MAP_KEY não estiver configurada, usa CSVs públicos como fallback.
    """
    if FIRMS_MAP_KEY:
        logger.info("FIRMS MAP_KEY detectada — usando API oficial")
        try:
            focos = await _coletar_focos_via_api(dias=dias)
            if focos:
                logger.info("API oficial retornou %d focos", len(focos))
                return focos
            else:
                logger.warning("API oficial retornou 0 focos — tentando fallback CSV")
        except Exception as e:
            logger.warning("API oficial falhou (%s) — tentando fallback CSV", e)
    else:
        logger.info("FIRMS MAP_KEY não configurada — usando CSVs públicos")

    return await _coletar_focos_csv_publico(dias=dias)


async def _coletar_focos_csv_publico(dias: int = 7) -> list[dict]:
    """
    Coleta focos reais do NASA FIRMS para o Ceará.
    Usa CSVs públicos sem necessidade de chave de API.
    Retorna lista de dicts prontos para serialização.
    """
    fontes_usar = []
    if dias <= 1:
        fontes_usar = ["VIIRS_SNPP_24h", "VIIRS_NOAA20_24h", "MODIS_24h"]
    else:
        fontes_usar = ["VIIRS_SNPP_7d", "VIIRS_NOAA20_7d", "MODIS_7d"]

    todos: list[dict] = []
    vistos: set[str] = set()  # deduplicação por lat+lon+data

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for nome_fonte in fontes_usar:
            url = FIRMS_SOURCES[nome_fonte]
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                reader = csv.DictReader(io.StringIO(resp.text))

                for row in reader:
                    try:
                        lat = float(row.get("latitude", 0))
                        lon = float(row.get("longitude", 0))
                    except (ValueError, TypeError):
                        continue

                    # Filtrar bounding box Ceará
                    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                        continue

                    acq_date = row.get("acq_date", "")
                    acq_time = row.get("acq_time", "0000")
                    data_hora = _parse_dt(acq_date, acq_time)

                    # Deduplicação
                    chave = f"{lat:.4f}_{lon:.4f}_{acq_date}"
                    if chave in vistos:
                        continue
                    vistos.add(chave)

                    confianca = _parse_confianca(row.get("confidence", ""))
                    frp = _safe_float(row.get("frp"))
                    temp_k = _safe_float(row.get("bright_ti4") or row.get("brightness"))

                    # Determina fonte/satélite
                    satelite = row.get("satellite", nome_fonte.split("_")[0])
                    if "VIIRS" in nome_fonte:
                        fonte_label = "NASA_FIRMS"
                        sensor = "VIIRS"
                    else:
                        fonte_label = "NASA_FIRMS"
                        sensor = "MODIS"

                    severidade = _classificar_severidade(frp, confianca)

                    foco = {
                        "id": _foco_id_estavel(lat, lon, data_hora.isoformat(), sensor, satelite),
                        "fonte": fonte_label,
                        "satelite": satelite,
                        "sensor": sensor,
                        "lat": lat,
                        "lon": lon,
                        "latitude": lat,
                        "longitude": lon,
                        "data_hora": data_hora.isoformat(),
                        "municipio": None,  # será preenchido pelo geocoder reverso
                        "confianca": confianca,
                        "frp": frp,
                        "temperatura_k": temp_k,
                        "severidade": severidade,
                        "daynight": row.get("daynight", ""),
                        "scan": _safe_float(row.get("scan")),
                        "track": _safe_float(row.get("track")),
                    }
                    todos.append(foco)

            except httpx.HTTPError as e:
                logger.warning("Erro ao baixar FIRMS %s: %s", nome_fonte, e)
            except Exception as e:
                logger.error("Erro inesperado FIRMS %s: %s", nome_fonte, e)

    logger.info("FIRMS real: %d focos coletados no Ceará", len(todos))
    return todos
