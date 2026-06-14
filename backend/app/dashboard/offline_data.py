"""
Módulo de dados offline para o Dashboard Streamlit — Queimadas Ceará
=====================================================================
Carrega dados dos CSVs FIRMS baixados e métricas GOES-16 JSON,
permitindo o dashboard funcionar sem a API FastAPI.

Uso:
    from offline_data import load_firms_csv, load_goes16_metrics, get_offline_data_inventory
"""

import os
import json
import csv
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Caminhos relativos ao diretório raiz do projeto ───────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKEND_DATA_DIR = os.path.join(BASE_DIR, "backend", "data")


def find_project_root() -> str:
    """Encontra o diretório raiz do projeto procurando por ceara-queimadas."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, "data")) and os.path.isdir(os.path.join(c, "backend")):
            return c
    # Fallback: usa o cwd
    return os.getcwd()


def get_data_dir() -> str:
    """Retorna o diretório de dados do projeto."""
    root = find_project_root()
    return os.path.join(root, "data")


def get_backend_data_dir() -> str:
    """Retorna o diretório backend/data."""
    root = find_project_root()
    return os.path.join(root, "backend", "data")


def get_goes16_eval_dir() -> Optional[str]:
    """Retorna o diretório de avaliação GOES-16."""
    d = os.path.join(get_data_dir(), "goes16_eval")
    if not os.path.isdir(d):
        d = os.path.join(get_data_dir(), "..", "data", "goes16_eval")
    return d if os.path.isdir(d) else None


def load_firms_csv(
    satellite: Optional[str] = None,
    bbox: Optional[dict] = None,
    max_rows: int = 10000,
) -> list[dict]:
    """
    Carrega dados dos CSVs FIRMS (24h) disponíveis no diretório data/.

    Parâmetros:
        satellite: Filtrar por satélite ('MODIS', 'VIIRS_SNPP', 'VIIRS_NOAA20',
                   'VIIRS_NOAA21' ou None para todos)
        bbox: Dicionário com lat_min, lat_max, lon_min, lon_max para filtrar
              por bounding box
        max_rows: Máximo de registros a retornar

    Retorna:
        Lista de dicionários com os dados dos focos
    """
    data_dir = get_data_dir()
    firms_files = {
        "MODIS": "firms_modis_24h.csv",
        "VIIRS_SNPP (Suomi NPP)": "firms_suomi_viirs_24h.csv",
        "VIIRS_NOAA20 (JPSS-1)": "firms_noaa20_viirs_24h.csv",
        "VIIRS_NOAA21 (JPSS-2)": "firms_noaa21_viirs_24h.csv",
    }

    selected = []
    if satellite:
        fname = firms_files.get(satellite)
        if fname:
            selected = [(satellite, os.path.join(data_dir, fname))]
    else:
        selected = [(name, os.path.join(data_dir, fname)) for name, fname in firms_files.items()]

    all_records = []
    for sat_name, fpath in selected:
        if not os.path.isfile(fpath):
            logger.warning(f"Arquivo não encontrado: {fpath}")
            continue
        try:
            with open(fpath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Converte campos numéricos
                    try:
                        lat = float(row.get("latitude", 0))
                        lon = float(row.get("longitude", 0))
                    except (ValueError, TypeError):
                        continue

                    # Filtro por bounding box
                    if bbox:
                        if not (bbox["lat_min"] <= lat <= bbox["lat_max"] and
                                bbox["lon_min"] <= lon <= bbox["lon_max"]):
                            continue

                    try:
                        frp = float(row.get("frp", 0))
                        confidence = int(row.get("confidence", 0))
                        brightness = float(row.get("brightness", 0))
                    except (ValueError, TypeError):
                        frp = 0
                        confidence = 0
                        brightness = 0

                    # Classifica severidade com base no FRP
                    if frp >= 50:
                        severidade = "critica"
                    elif frp >= 20:
                        severidade = "alta"
                    elif frp >= 10:
                        severidade = "media"
                    else:
                        severidade = "baixa"

                    all_records.append({
                        "latitude": lat,
                        "longitude": lon,
                        "frp": frp,
                        "severidade": severidade,
                        "confianca": min(confidence, 100),
                        "brightness": brightness,
                        "satelite": sat_name,
                        "sensor": "VIIRS" if "VIIRS" in sat_name else "MODIS",
                        "data_hora": f"{row.get('acq_date', '')} {row.get('acq_time', '')}",
                        "municipio": _reverse_geocode_approximate(lat, lon),
                        "daynight": row.get("daynight", "?"),
                        "acq_date": row.get("acq_date", ""),
                        "acq_time": row.get("acq_time", ""),
                    })

                    if len(all_records) >= max_rows:
                        break
        except Exception as e:
            logger.error(f"Erro ao ler {fpath}: {e}")

    return all_records


# Municípios aproximados do Ceará para geocodificação reversa simples
# (lat_center, lon_center, nome)
_CEARA_CITIES = [
    (-3.7172, -38.5434, "Fortaleza"),
    (-3.8278, -38.4742, "Caucaia"),
    (-3.8833, -38.6333, "Maracanaú"),
    (-3.7450, -38.4708, "Eusébio"),
    (-3.8000, -38.5833, "Maranguape"),
    (-5.0892, -39.5778, "Quixeramobim"),
    (-5.1928, -39.5186, "Senador Pompeu"),
    (-5.5300, -39.2200, "Iguatu"),
    (-6.7667, -39.2667, "Juazeiro do Norte"),
    (-7.2333, -39.4000, "Crato"),
    (-7.2833, -39.2667, "Barbalha"),
    (-4.9633, -39.0183, "Quixadá"),
    (-4.8692, -38.9708, "Baturité"),
    (-4.5642, -39.0764, "Canindé"),
    (-5.1983, -39.0856, "Solonópole"),
    (-4.1333, -38.2333, "Cascavel"),
    (-4.4500, -37.6667, "Aracati"),
    (-4.5333, -37.7833, "Icapuí"),
    (-3.0333, -39.5167, "Itapipoca"),
    (-3.3667, -38.9500, "São Gonçalo do Amarante"),
    (-3.6000, -38.9667, "Paracuru"),
    (-3.3300, -39.3200, "Uruburetama"),
    (-2.9000, -40.1167, "Acaraú"),
    (-2.7833, -40.5000, "Cruz"),
    (-2.8500, -40.0667, "Jijoca de Jericoacoara"),
    (-3.1500, -39.9833, "Amontada"),
    (-5.4000, -38.0000, "Limoeiro do Norte"),
    (-5.2000, -37.7667, "Russas"),
    (-5.2500, -37.9833, "Jaguaruana"),
    (-4.8500, -37.7833, "Palhano"),
    (-5.0950, -38.3744, "Morada Nova"),
    (-6.1833, -38.4667, "Pau dos Ferros (RN)"),
    (-4.5561, -37.9647, "Beberibe"),
    (-5.5667, -37.7833, "Apodi (RN)"),
    (-5.4772, -39.0747, "Milhã"),
    (-5.4931, -39.5953, "Deputado Irapuan Pinheiro"),
    (-6.7361, -39.8856, "Campos Sales"),
    (-7.0025, -39.5117, "Farias Brito"),
    (-7.2000, -39.0000, "Missão Velha"),
    (-6.0333, -39.2833, "Jaguaribe"),
    (-6.6667, -39.5167, "Icó"),
    (-5.6600, -39.6300, "Piquet Carneiro"),
    (-5.4200, -39.7300, "Boa Viagem"),
    (-5.6500, -38.2667, "São Miguel"),
    (-4.8500, -39.1833, "Santa Quitéria"),
    (-3.7167, -40.3500, "Sobral"),
    (-3.5383, -40.5833, "Massapê"),
    (-3.6500, -40.2000, "Santana do Acaraú"),
    (-4.1333, -40.5333, "Crateús"),
    (-4.5833, -40.1167, "Tamboril"),
    (-5.1667, -40.1833, "Catunda"),
    (-5.1167, -40.6667, "Novo Oriente"),
    (-5.5833, -40.7000, "Quiterianópolis"),
    (-6.0167, -40.1833, "Tauá"),
    (-4.7000, -38.4833, "Pacajus"),
    (-4.6500, -38.5500, "Horizonte"),
    (-4.1833, -38.6333, "São Bento do Norte"),
    (-2.8833, -41.2333, "Parnaíba (PI)"),
    (-4.8889, -39.2725, "Itapiúna"),
    (-4.1333, -38.8667, "Ocara"),
    (-4.2833, -39.1833, "Aracoiaba"),
]

# Cidades de estados vizinhos que aparecem na borda
_NEARBY_CITIES = [
    (-6.9833, -42.8833, "Oeiras (PI)"),
    (-7.0833, -42.7167, "Floriano (PI)"),
    (-7.1167, -42.5500, "Nazaré do Piauí (PI)"),
    (-6.2500, -42.0333, "Elesbão Veloso (PI)"),
    (-5.5333, -42.6167, "Barras (PI)"),
    (-7.1167, -43.1500, "Jerumenha (PI)"),
    (-6.7500, -43.0333, "São Francisco (PI)"),
    (-5.0989, -37.9860, "Mossoró (RN)"),
    (-6.1500, -37.3167, "Patu (RN)"),
    (-3.9000, -42.0000, "Piripiri (PI)"),
    (-4.2833, -37.4167, "Tibau (RN)"),
    (-3.0167, -41.1333, "Cajueiro da Praia (PI)"),
]

_ALL_CITIES = _CEARA_CITIES + _NEARBY_CITIES


def _reverse_geocode_approximate(lat: float, lon: float) -> str:
    """Geocodificação reversa aproximada: encontra o município mais próximo."""
    min_dist = float("inf")
    closest = "?"
    for clat, clon, name in _ALL_CITIES:
        d = (lat - clat) ** 2 + (lon - clon) ** 2
        if d < min_dist:
            min_dist = d
            closest = name
    # Se estiver muito longe, retorna genérico
    if min_dist > 5.0:  # ~2.2 graus de distância
        closest = "Interior"
    return closest


def load_goes16_metrics(metric_file: Optional[str] = None) -> dict:
    """
    Carrega métricas de avaliação GOES-16 dos JSONs em goes16_eval/.

    Parâmetros:
        metric_file: Nome do arquivo (ex: 'metrics_2024-10-31.json').
                     Se None, carrega o mais recente.

    Retorna:
        Dicionário com as métricas ou dict vazio se não encontrado.
    """
    eval_dir = get_goes16_eval_dir()
    if not eval_dir:
        return {"error": "Diretório goes16_eval não encontrado"}

    json_files = sorted([f for f in os.listdir(eval_dir) if f.startswith("metrics_") and f.endswith(".json")])

    if not json_files:
        return {"error": "Nenhum arquivo de métricas encontrado"}

    if metric_file and metric_file in json_files:
        fpath = os.path.join(eval_dir, metric_file)
    else:
        fpath = os.path.join(eval_dir, json_files[-1])

    try:
        with open(fpath) as f:
            data = json.load(f)
        data["_source_file"] = os.path.basename(fpath)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_eval_maps() -> list[dict]:
    """Lista os mapas disponíveis em goes16_eval/maps/."""
    data_dir = get_data_dir()
    maps_dir = os.path.join(data_dir, "goes16_eval", "maps")
    if not os.path.isdir(maps_dir):
        return []
    maps = []
    for fname in sorted(os.listdir(maps_dir)):
        if fname.endswith(".png"):
            maps.append({
                "name": fname,
                "path": os.path.abspath(os.path.join(maps_dir, fname)),
                "size_kb": round(os.path.getsize(os.path.join(maps_dir, fname)) / 1024, 1),
            })
    return maps


def get_offline_data_inventory() -> dict:
    """
    Retorna inventário completo dos dados disponíveis offline.

    Retorna:
        Dicionário com as seções: firms_csvs, goes16_metrics, eval_maps, analysis_jsons
    """
    data_dir = get_data_dir()

    # CSVs FIRMS
    firms_csvs = []
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv") and "firms" in fname:
            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath) as f:
                    lines = sum(1 for _ in f)
            except Exception:
                lines = 0
            firms_csvs.append({
                "name": fname,
                "rows": lines - 1,  # menos header
                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
            })

    # JSONs de análise
    analysis_jsons = []
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".json") and "firms_analysis" in fname:
            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath) as f:
                    analysis = json.load(f)
            except Exception:
                analysis = {}
            analysis_jsons.append({
                "name": fname,
                "total": analysis.get("total_hotspots", 0),
                "timestamp": analysis.get("timestamp", ""),
                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
            })

    # GOES-16 metrics
    eval_dir = get_goes16_eval_dir()
    goes16_metrics = []
    if eval_dir:
        for fname in sorted(os.listdir(eval_dir)):
            if fname.startswith("metrics_") and fname.endswith(".json"):
                fpath = os.path.join(eval_dir, fname)
                goes16_metrics.append({
                    "name": fname,
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                })

    # Mapas
    eval_maps = get_eval_maps()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "firms_csvs": firms_csvs,
        "analysis_jsons": analysis_jsons,
        "goes16_metrics": goes16_metrics,
        "eval_maps": eval_maps,
        "total_records": sum(c["rows"] for c in firms_csvs),
    }
