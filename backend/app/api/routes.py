"""
Rotas FastAPI da plataforma de queimadas do Ceará.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.orm_models import (
    AlertaQueimadaORM,
    EventoQueimadaORM,
    FocoQueimadaORM,
    LeituraGOES16ORM,
    RiscoMunicipalORM,
)
from app.models.schemas import (
    AlertaQueimada,
    BoletimTecnico,
    EventoQueimada,
    FocoQueimada,
    RespostaAgente,
    RiscoMunicipal,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Focos de Queimada
# ---------------------------------------------------------------------------

@router.get("/focos/tempo-real", response_model=list[dict], tags=["Focos"])
async def focos_tempo_real(
    horas: int = Query(default=6, ge=1, le=72, description="Janela de tempo em horas"),
    fonte: Optional[str] = Query(default=None, description="INPE, NASA_FIRMS ou GOES16"),
    db: AsyncSession = Depends(get_db),
):
    """Retorna focos de queimada recentes no Ceará."""
    from datetime import timezone
    filtros = [
        FocoQueimadaORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=horas)
    ]
    if fonte:
        filtros.append(FocoQueimadaORM.fonte == fonte.upper())

    from sqlalchemy import and_
    result = await db.execute(
        select(FocoQueimadaORM).where(and_(*filtros)).order_by(desc(FocoQueimadaORM.data_hora)).limit(500)
    )
    focos = result.scalars().all()
    return [
        {
            "id": f.id,
            "fonte": f.fonte,
            "lat": f.latitude,
            "lon": f.longitude,
            "municipio": f.municipio,
            "data_hora": f.data_hora.isoformat() if f.data_hora else None,
            "severidade": f.severidade,
            "frp": f.frp,
            "confianca": f.confianca,
            "temperatura_k": f.temperatura_k,
        }
        for f in focos
    ]


@router.get("/focos/municipio/{municipio}", response_model=list[dict], tags=["Focos"])
async def focos_por_municipio(
    municipio: str,
    horas: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Retorna focos de queimada de um município específico."""
    from datetime import timezone
    from sqlalchemy import and_
    result = await db.execute(
        select(FocoQueimadaORM).where(
            and_(
                FocoQueimadaORM.municipio.ilike(f"%{municipio}%"),
                FocoQueimadaORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=horas),
            )
        ).order_by(desc(FocoQueimadaORM.data_hora))
    )
    focos = result.scalars().all()
    return [
        {
            "id": f.id,
            "fonte": f.fonte,
            "lat": f.latitude,
            "lon": f.longitude,
            "data_hora": f.data_hora.isoformat() if f.data_hora else None,
            "severidade": f.severidade,
            "frp": f.frp,
        }
        for f in focos
    ]


# ---------------------------------------------------------------------------
# Risco Municipal
# ---------------------------------------------------------------------------

@router.get("/risco/municipios", response_model=list[dict], tags=["Risco"])
async def ranking_risco_municipios(
    limite: int = Query(default=20, ge=1, le=184),
    db: AsyncSession = Depends(get_db),
):
    """Retorna ranking de municípios por índice de risco de queimada."""
    subq = (
        select(
            RiscoMunicipalORM.municipio,
            func.max(RiscoMunicipalORM.data_calculo).label("ultima"),
        )
        .group_by(RiscoMunicipalORM.municipio)
        .subquery()
    )
    result = await db.execute(
        select(RiscoMunicipalORM)
        .join(
            subq,
            (RiscoMunicipalORM.municipio == subq.c.municipio)
            & (RiscoMunicipalORM.data_calculo == subq.c.ultima),
        )
        .order_by(desc(RiscoMunicipalORM.indice_risco))
        .limit(limite)
    )
    riscos = result.scalars().all()
    return [
        {
            "posicao": i + 1,
            "municipio": r.municipio,
            "indice_risco": r.indice_risco,
            "classificacao": r.classificacao,
            "focos_24h": r.focos_24h,
            "focos_7d": r.focos_7d,
            "dias_sem_chuva": r.dias_sem_chuva,
            "umidade_media": r.umidade_media,
            "justificativa": r.justificativa,
        }
        for i, r in enumerate(riscos)
    ]


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------

@router.get("/alertas/ativos", response_model=list[dict], tags=["Alertas"])
async def alertas_ativos(
    nivel: Optional[str] = Query(default=None, description="informativo/atencao/alerta/emergencia"),
    db: AsyncSession = Depends(get_db),
):
    """Lista alertas ativos de queimadas."""
    from datetime import timezone
    from sqlalchemy import and_
    filtros = [
        AlertaQueimadaORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=48)
    ]
    if nivel:
        filtros.append(AlertaQueimadaORM.nivel == nivel)

    result = await db.execute(
        select(AlertaQueimadaORM).where(and_(*filtros)).order_by(desc(AlertaQueimadaORM.data_hora))
    )
    alertas = result.scalars().all()
    return [
        {
            "id_alerta": a.id_alerta,
            "nivel": a.nivel,
            "municipio": a.municipio,
            "mensagem": a.mensagem,
            "recomendacao": a.recomendacao,
            "data_hora": a.data_hora.isoformat() if a.data_hora else None,
            "nivel_confianca": a.nivel_confianca,
            "auditado": a.auditado,
        }
        for a in alertas
    ]


# ---------------------------------------------------------------------------
# GOES-16
# ---------------------------------------------------------------------------

@router.get("/goes16/eventos", response_model=list[dict], tags=["GOES-16"])
async def eventos_goes16(
    horas: int = Query(default=6, ge=1, le=48),
    municipio: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retorna eventos detectados pelo GOES-16."""
    from datetime import timezone
    from sqlalchemy import and_
    filtros = [
        LeituraGOES16ORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=horas),
        LeituraGOES16ORM.mascara_fogo == True,
    ]
    if municipio:
        filtros.append(LeituraGOES16ORM.municipio.ilike(f"%{municipio}%"))

    result = await db.execute(
        select(LeituraGOES16ORM).where(and_(*filtros)).order_by(desc(LeituraGOES16ORM.data_hora)).limit(100)
    )
    leituras = result.scalars().all()
    return [
        {
            "id": l.id,
            "data_hora": l.data_hora.isoformat() if l.data_hora else None,
            "lat": l.latitude,
            "lon": l.longitude,
            "municipio": l.municipio,
            "temperatura_k": l.temperatura_pixel_k,
            "frp_mw": l.frp_mw,
            "persistencia_horas": l.persistencia_horas,
            "deteccoes_consecutivas": l.deteccoes_consecutivas,
        }
        for l in leituras
    ]


# ---------------------------------------------------------------------------
# Agente / Chat
# ---------------------------------------------------------------------------

@router.post("/agente/pergunta", response_model=dict, tags=["Agente IA"])
async def pergunta_agente(payload: dict):
    """
    Permite perguntas em linguagem natural ao agente ReAct.
    Exemplo: {"pergunta": "Quais municípios estão com risco crítico hoje?"}
    """
    pergunta = payload.get("pergunta", "").strip()
    if not pergunta:
        raise HTTPException(status_code=400, detail="Campo 'pergunta' é obrigatório")

    from app.agents.react_agent import diagnosticar
    resposta = await diagnosticar(pergunta)
    return resposta.model_dump()


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

@router.get("/relatorios/boletim", response_model=dict, tags=["Relatórios"])
async def gerar_boletim(
    municipio: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Gera boletim técnico de queimadas."""
    from app.agents.langgraph_pipeline import construir_grafo

    grafo = construir_grafo()
    estado_inicial: dict = {
        "focos_brutos": [],
        "leituras_goes16": [],
        "dados_climaticos": [],
        "focos_validados": [],
        "leituras_goes16_validadas": [],
        "dados_climaticos_validados": [],
        "focos_enriquecidos": [],
        "analise_goes16": {},
        "analise_climatica": {},
        "evidencias_fundidas": {},
        "eventos_consolidados": [],
        "riscos_municipais": [],
        "alertas": [],
        "diagnostico": "",
        "boletim": "",
        "erros": [],
        "timestamp_inicio": "",
    }
    resultado = await grafo.ainvoke(estado_inicial)
    return {
        "boletim": resultado.get("boletim", ""),
        "total_eventos": len(resultado.get("eventos_consolidados", [])),
        "total_alertas": len(resultado.get("alertas", [])),
        "erros": resultado.get("erros", []),
    }


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

@router.get("/eventos/{evento_id}", response_model=dict, tags=["Eventos"])
async def detalhe_evento(evento_id: str, db: AsyncSession = Depends(get_db)):
    """Detalha um evento de queimada consolidado."""
    result = await db.execute(
        select(EventoQueimadaORM).where(EventoQueimadaORM.id_evento == evento_id)
    )
    evento = result.scalar_one_or_none()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    return {
        "id_evento": evento.id_evento,
        "municipio": evento.municipio,
        "lat": evento.latitude_centroide,
        "lon": evento.longitude_centroide,
        "fontes": evento.fontes,
        "inicio": evento.inicio.isoformat() if evento.inicio else None,
        "ultima_deteccao": evento.ultima_deteccao.isoformat() if evento.ultima_deteccao else None,
        "quantidade_focos": evento.quantidade_focos,
        "severidade": evento.severidade,
        "confianca": evento.confianca,
        "goes16_confirmado": evento.goes16_confirmado,
        "inpe_confirmado": evento.inpe_confirmado,
        "firms_confirmado": evento.firms_confirmado,
        "justificativa": evento.justificativa,
        "proxima_uc": evento.proxima_uc,
        "distancia_uc_km": evento.distancia_uc_km,
    }


# ---------------------------------------------------------------------------
# Camadas de mapa
# ---------------------------------------------------------------------------

@router.get("/mapa/camadas", response_model=list[dict], tags=["Mapa"])
async def listar_camadas():
    """Lista camadas disponíveis para o mapa interativo."""
    return [
        {"id": "focos_inpe", "nome": "Focos INPE", "tipo": "pontos", "ativo": True},
        {"id": "focos_firms", "nome": "Focos NASA FIRMS", "tipo": "pontos", "ativo": True},
        {"id": "goes16", "nome": "GOES-16 Fogo", "tipo": "pontos", "ativo": True},
        {"id": "risco_municipal", "nome": "Risco Municipal", "tipo": "poligonos", "ativo": True},
        {"id": "municipios", "nome": "Municípios CE", "tipo": "poligonos", "ativo": True},
        {"id": "ucs", "nome": "Unidades de Conservação", "tipo": "poligonos", "ativo": False},
        {"id": "mapbiomas_fogo", "nome": "MapBiomas Fogo (histórico)", "tipo": "raster", "ativo": False},
        {"id": "heatmap", "nome": "Heatmap de Concentração", "tipo": "heatmap", "ativo": False},
    ]
