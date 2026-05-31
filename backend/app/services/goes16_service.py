"""
Serviço de coleta e processamento de dados GOES-16 (produto ABI-L2-FDCF).
Acessa o bucket S3 público da NOAA.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from app.core.config import settings
from app.models.schemas import LeituraGOES16

logger = logging.getLogger(__name__)

S3_BUCKET = settings.GOES16_S3_BUCKET
PRODUTO = settings.GOES16_PRODUCT  # ABI-L2-FDCF


def _s3_client():
    """Cria cliente S3 sem autenticação (bucket público NOAA)."""
    return boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(signature_version=UNSIGNED),
    )


def _prefixo_goes16(dt: datetime, produto: str = PRODUTO) -> str:
    """Monta o prefixo S3 para o produto GOES-16 em determinada hora."""
    return f"{produto}/{dt.year}/{dt.timetuple().tm_yday:03d}/{dt.hour:02d}/"


async def listar_arquivos_goes16(horas_atras: int = 2) -> list[str]:
    """Lista arquivos NetCDF do GOES-16 nas últimas N horas."""
    s3 = _s3_client()
    agora = datetime.now(timezone.utc)
    chaves: list[str] = []

    for h in range(horas_atras):
        dt = agora - timedelta(hours=h)
        prefixo = _prefixo_goes16(dt)
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefixo)
            for obj in resp.get("Contents", []):
                chaves.append(obj["Key"])
        except Exception as e:
            logger.warning("Erro ao listar GOES-16 S3 (%s): %s", prefixo, e)

    return chaves


async def processar_arquivo_goes16(chave_s3: str) -> list[LeituraGOES16]:
    """
    Baixa e processa um arquivo NetCDF do GOES-16.
    Extrai pixels com máscara de fogo dentro do bounding box do Ceará.
    Requer: netCDF4, numpy
    """
    import io
    import tempfile

    import netCDF4 as nc
    import numpy as np

    s3 = _s3_client()
    leituras: list[LeituraGOES16] = []

    try:
        with tempfile.NamedTemporaryFile(suffix=".nc") as tmp:
            s3.download_fileobj(S3_BUCKET, chave_s3, tmp)
            tmp.flush()

            ds = nc.Dataset(tmp.name)

            # Coordenadas
            lats = ds.variables.get("latitude") or ds.variables.get("lat")
            lons = ds.variables.get("longitude") or ds.variables.get("lon")
            mask = ds.variables.get("Mask") or ds.variables.get("Fire_Mask")
            temp = ds.variables.get("Temp") or ds.variables.get("DQF")
            frp_var = ds.variables.get("Power") or ds.variables.get("FRP")

            if lats is None or lons is None or mask is None:
                logger.warning("Variáveis esperadas não encontradas em %s", chave_s3)
                return []

            lat_arr = np.array(lats[:])
            lon_arr = np.array(lons[:])
            mask_arr = np.array(mask[:])

            # Filtrar bounding box Ceará
            idx = np.where(
                (lat_arr >= settings.CEARA_LAT_MIN)
                & (lat_arr <= settings.CEARA_LAT_MAX)
                & (lon_arr >= settings.CEARA_LON_MIN)
                & (lon_arr <= settings.CEARA_LON_MAX)
                & (mask_arr > 0)
            )

            # Extrair timestamp do nome do arquivo
            # Formato: ...s20231234500000...
            data_hora = _extrair_timestamp_goes16(chave_s3)

            for i in zip(*idx):
                idx_flat = i[0] if len(i) == 1 else i
                leitura = LeituraGOES16(
                    id=str(uuid4()),
                    data_hora=data_hora,
                    latitude=float(lat_arr[idx_flat]),
                    longitude=float(lon_arr[idx_flat]),
                    mascara_fogo=bool(mask_arr[idx_flat] > 0),
                    temperatura_pixel_k=float(temp[idx_flat]) if temp is not None else None,
                    frp_mw=float(frp_var[idx_flat]) if frp_var is not None else None,
                    produto=PRODUTO,
                )
                leituras.append(leitura)

            ds.close()

    except Exception as e:
        logger.error("Erro ao processar GOES-16 %s: %s", chave_s3, e)

    logger.info("GOES-16: %d leituras extraídas de %s", len(leituras), chave_s3)
    return leituras


def _extrair_timestamp_goes16(chave: str) -> datetime:
    """Extrai timestamp do nome do arquivo GOES-16 (formato sYYYYDDDHHMMSSS)."""
    import re

    match = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", chave)
    if match:
        ano, dia_ano, hora, minuto, segundo = match.groups()
        base = datetime(int(ano), 1, 1, tzinfo=timezone.utc)
        return base + timedelta(
            days=int(dia_ano) - 1,
            hours=int(hora),
            minutes=int(minuto),
            seconds=int(segundo),
        )
    return datetime.now(timezone.utc)


async def coletar_dados_goes16(horas_atras: int = 2) -> list[LeituraGOES16]:
    """Pipeline completo: lista arquivos e processa cada um."""
    arquivos = await listar_arquivos_goes16(horas_atras)
    todas: list[LeituraGOES16] = []
    for arq in arquivos[:10]:  # limita para não sobrecarregar
        leituras = await processar_arquivo_goes16(arq)
        todas.extend(leituras)
    return todas
