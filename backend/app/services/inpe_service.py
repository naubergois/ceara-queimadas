"""
Serviço de coleta de focos de queimada do INPE BDQueimadas.
Fonte: CSV públicos do dataserver-coids.inpe.br (nova URL após migração do TerraBrasilis).
URL antiga (desativada): https://queimadas.dgi.inpe.br/api → redireciona 301 para terrabrasilis (que retorna 404)
URL nova: https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/
"""

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from pydantic import ValidationError

from app.models.schemas import FocoQueimada

logger = logging.getLogger(__name__)

# Nova URL dos dados INPE — CSV diário do Brasil
INPE_CSV_BASE = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil"
# Fallback: dados de 10 min (NRT)
INPE_CSV_10MIN_BASE = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/10min"


async def coletar_focos_inpe(
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    estado: str = "CE",
) -> list[FocoQueimada]:
    """
    Coleta focos de queimada do INPE BDQueimadas para o Ceará.
    Usa CSVs públicos do dataserver-coids.inpe.br.
    Retorna lista de FocoQueimada validados com Pydantic.
    """
    agora = datetime.now(timezone.utc)
    if data_fim is None:
        data_fim = agora
    if data_inicio is None:
        data_inicio = agora - timedelta(hours=24)

    focos: list[FocoQueimada] = []

    # Baixa CSVs diários para cada dia no período
    data_corrente = data_inicio
    while data_corrente <= data_fim:
        data_str = data_corrente.strftime("%Y%m%d")
        url = f"{INPE_CSV_BASE}/focos_diario_br_{data_str}.csv"

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                content = response.text

            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                try:
                    estado_row = (row.get("estado") or "").strip().upper()
                    # Suporta tanto "CEARÁ" quanto "CE"
                    estado_nome = _estado_map(estado)
                    if estado_row != estado and estado_row != estado_nome:
                        continue

                    lat = float(row.get("lat", 0))
                    lon = float(row.get("lon", 0))

                    # Pular linhas sem coordenadas válidas
                    if abs(lat) < 0.01 and abs(lon) < 0.01:
                        continue

                    data_hora_str = (row.get("data_hora_gmt") or "").strip()
                    data_hora = _parse_inpe_datetime(data_hora_str) if data_hora_str else agora

                    foco = FocoQueimada(
                        fonte="INPE",
                        latitude=lat,
                        longitude=lon,
                        data_hora=data_hora,
                        municipio=(row.get("municipio") or "").strip() or None,
                        estado=estado,
                        bioma=(row.get("bioma") or "").strip() or None,
                        satelite=(row.get("satelite") or "").strip() or None,
                        confianca=_safe_float(row.get("risco_fogo")),
                        frp=_safe_float(row.get("frp")),
                    )
                    focos.append(foco)
                except (ValidationError, ValueError, TypeError) as e:
                    logger.warning("Foco INPE inválido ignorado: %s | erro: %s", row, e)

        except httpx.HTTPError as e:
            logger.warning("Erro ao baixar CSV INPE %s: %s", data_str, e)
        except Exception as e:
            logger.error("Erro inesperado INPE %s: %s", data_str, e)

        data_corrente += timedelta(days=1)

    logger.info("INPE CSV: %d focos coletados para %s", len(focos), estado)
    return focos


def _estado_map(sigla: str) -> str:
    """Mapeia sigla para nome completo do estado (usado nos CSVs do INPE)."""
    mapa = {
        "AC": "ACRE", "AL": "ALAGOAS", "AP": "AMAPÁ", "AM": "AMAZONAS",
        "BA": "BAHIA", "CE": "CEARÁ", "DF": "DISTRITO FEDERAL",
        "ES": "ESPÍRITO SANTO", "GO": "GOIÁS", "MA": "MARANHÃO",
        "MT": "MATO GROSSO", "MS": "MATO GROSSO DO SUL", "MG": "MINAS GERAIS",
        "PA": "PARÁ", "PB": "PARAÍBA", "PR": "PARANÁ", "PE": "PERNAMBUCO",
        "PI": "PIAUÍ", "RJ": "RIO DE JANEIRO", "RN": "RIO GRANDE DO NORTE",
        "RS": "RIO GRANDE DO SUL", "RO": "RONDÔNIA", "RR": "RORAIMA",
        "SC": "SANTA CATARINA", "SP": "SÃO PAULO", "SE": "SERGIPE",
        "TO": "TOCANTINS",
    }
    return mapa.get(sigla.upper(), sigla)


def _parse_inpe_datetime(value: str) -> datetime:
    """Parse data/hora no formato 'YYYY-MM-DD HH:MM:SS'."""
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _safe_float(value) -> Optional[float]:
    try:
        if value is not None and str(value).strip():
            return float(value)
    except (ValueError, TypeError):
        pass
    return None
