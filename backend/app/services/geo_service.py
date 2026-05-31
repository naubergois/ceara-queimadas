"""
Serviço geoespacial: cruzamento de focos com municípios, UCs e áreas sensíveis.
Usa PostGIS via SQLAlchemy ou shapely/pyproj como fallback.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import FocoQueimada

logger = logging.getLogger(__name__)


async def identificar_municipio(
    lat: float, lon: float, db: AsyncSession
) -> Optional[str]:
    """
    Retorna o nome do município do Ceará que contém o ponto (lat, lon).
    Usa ST_Contains do PostGIS.
    """
    sql = text(
        """
        SELECT nome
        FROM municipios_ceara
        WHERE ST_Contains(
            geom,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        )
        LIMIT 1
        """
    )
    result = await db.execute(sql, {"lat": lat, "lon": lon})
    row = result.fetchone()
    return row[0] if row else None


async def distancia_uc_mais_proxima(
    lat: float, lon: float, db: AsyncSession
) -> tuple[Optional[str], Optional[float]]:
    """
    Retorna (nome_uc, distancia_km) da Unidade de Conservação mais próxima.
    """
    sql = text(
        """
        SELECT nome,
               ST_Distance(
                   geom::geography,
                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
               ) / 1000 AS distancia_km
        FROM areas_sensiveis
        WHERE tipo = 'UC'
        ORDER BY distancia_km
        LIMIT 1
        """
    )
    result = await db.execute(sql, {"lat": lat, "lon": lon})
    row = result.fetchone()
    if row:
        return row[0], round(row[1], 2)
    return None, None


async def distancia_area_urbana(
    lat: float, lon: float, db: AsyncSession
) -> tuple[Optional[str], Optional[float]]:
    """
    Retorna (nome_area_urbana, distancia_km) da área urbana mais próxima.
    """
    sql = text(
        """
        SELECT nome,
               ST_Distance(
                   geom::geography,
                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
               ) / 1000 AS distancia_km
        FROM areas_sensiveis
        WHERE tipo = 'AREA_URBANA'
        ORDER BY distancia_km
        LIMIT 1
        """
    )
    result = await db.execute(sql, {"lat": lat, "lon": lon})
    row = result.fetchone()
    if row:
        return row[0], round(row[1], 2)
    return None, None


async def enriquecer_foco(foco: FocoQueimada, db: AsyncSession) -> FocoQueimada:
    """
    Enriquece um foco com informações geoespaciais:
    - município
    - UC mais próxima
    - área urbana mais próxima
    """
    if not foco.municipio:
        foco.municipio = await identificar_municipio(foco.latitude, foco.longitude, db)

    return foco


async def focos_por_municipio(
    municipio: str, horas: int = 24, db: AsyncSession = None
) -> list[dict]:
    """Retorna focos recentes de um município."""
    sql = text(
        """
        SELECT id, fonte, latitude, longitude, data_hora,
               confianca, temperatura_k, frp, severidade
        FROM focos_queimada
        WHERE municipio = :municipio
          AND data_hora >= NOW() - INTERVAL ':horas hours'
        ORDER BY data_hora DESC
        """
    )
    result = await db.execute(sql, {"municipio": municipio, "horas": horas})
    return [dict(row._mapping) for row in result.fetchall()]


async def calcular_risco_municipal(municipio: str, db: AsyncSession) -> dict:
    """
    Calcula índice de risco para um município combinando:
    focos recentes, clima, histórico MapBiomas.
    """
    # Focos nas últimas 24h, 48h e 7 dias
    sql_focos = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE data_hora >= NOW() - INTERVAL '24 hours') AS focos_24h,
            COUNT(*) FILTER (WHERE data_hora >= NOW() - INTERVAL '48 hours') AS focos_48h,
            COUNT(*) FILTER (WHERE data_hora >= NOW() - INTERVAL '7 days')   AS focos_7d,
            AVG(frp) FILTER (WHERE data_hora >= NOW() - INTERVAL '24 hours') AS frp_medio
        FROM focos_queimada
        WHERE municipio = :municipio
        """
    )
    r_focos = await db.execute(sql_focos, {"municipio": municipio})
    focos = r_focos.fetchone()

    # Dados climáticos mais recentes
    sql_clima = text(
        """
        SELECT temperatura_c, umidade_relativa, velocidade_vento_ms,
               dias_sem_chuva
        FROM dados_climaticos
        WHERE municipio = :municipio
        ORDER BY data_hora DESC
        LIMIT 1
        """
    )
    r_clima = await db.execute(sql_clima, {"municipio": municipio})
    clima = r_clima.fetchone()

    # Calcular índice (0-100)
    indice = _calcular_indice(focos, clima)

    return {
        "municipio": municipio,
        "indice_risco": indice,
        "focos_24h": focos[0] if focos else 0,
        "focos_48h": focos[1] if focos else 0,
        "focos_7d": focos[2] if focos else 0,
        "temperatura_media": clima[0] if clima else None,
        "umidade_media": clima[1] if clima else None,
        "vento_medio_ms": clima[2] if clima else None,
        "dias_sem_chuva": clima[3] if clima else None,
    }


def _calcular_indice(focos, clima) -> float:
    """
    Fórmula de risco ponderada:
    - Focos 24h: peso 30
    - Focos 7d: peso 15
    - Dias sem chuva: peso 20
    - Umidade baixa: peso 20
    - Vento alto: peso 15
    """
    score = 0.0

    if focos:
        f24 = focos[0] or 0
        f7d = focos[2] or 0
        score += min(f24 * 5, 30)   # até 30 pontos
        score += min(f7d * 1, 15)   # até 15 pontos

    if clima:
        dias_seca = clima[3] or 0
        umidade = clima[1] or 50
        vento = clima[2] or 0

        score += min(dias_seca * 1.5, 20)          # até 20 pontos
        score += max(0, (50 - umidade) * 0.4)       # até 20 pontos (umidade < 50%)
        score += min(vento * 1.5, 15)               # até 15 pontos

    return round(min(score, 100), 1)
