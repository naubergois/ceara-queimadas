"""
Pipeline LangGraph para orquestração dos agentes de queimadas.
Implementa o grafo completo: coleta → validação → análise → alerta.
"""

import logging
from datetime import datetime
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.core.config import settings
from app.models.schemas import (
    AlertaQueimada,
    DadoClimatico,
    EventoQueimada,
    FocoQueimada,
    LeituraGOES16,
    RiscoMunicipal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estado do grafo
# ---------------------------------------------------------------------------

class EstadoPipeline(TypedDict):
    """Estado compartilhado entre todos os nós do grafo LangGraph."""
    # Dados coletados
    focos_brutos: list[dict]
    leituras_goes16: list[dict]
    dados_climaticos: list[dict]

    # Dados validados
    focos_validados: list[FocoQueimada]
    leituras_goes16_validadas: list[LeituraGOES16]
    dados_climaticos_validados: list[DadoClimatico]

    # Análises
    focos_enriquecidos: list[dict]
    analise_goes16: dict
    analise_climatica: dict
    evidencias_fundidas: dict

    # Resultados
    eventos_consolidados: list[EventoQueimada]
    riscos_municipais: list[RiscoMunicipal]
    alertas: list[AlertaQueimada]
    diagnostico: str
    boletim: str

    # Controle
    erros: list[str]
    timestamp_inicio: str


# ---------------------------------------------------------------------------
# Nós do grafo
# ---------------------------------------------------------------------------

async def no_coletar_dados(estado: EstadoPipeline) -> dict:
    """Coleta dados de todas as fontes: INPE, NASA FIRMS, GOES-16, clima."""
    logger.info("[LangGraph] Coletando dados...")
    from app.services.inpe_service import coletar_focos_inpe
    from app.services.firms_service import coletar_focos_firms
    from app.services.clima_service import coletar_clima_funceme

    focos_inpe = await coletar_focos_inpe()
    focos_firms = await coletar_focos_firms()
    dados_clima = await coletar_clima_funceme()

    focos_brutos = [f.model_dump() for f in focos_inpe + focos_firms]
    clima_brutos = [d.model_dump() for d in dados_clima]

    logger.info("[LangGraph] Coletados: %d focos, %d dados climáticos", len(focos_brutos), len(clima_brutos))
    return {
        "focos_brutos": focos_brutos,
        "dados_climaticos": clima_brutos,
        "timestamp_inicio": datetime.utcnow().isoformat(),
    }


async def no_validar_dados(estado: EstadoPipeline) -> dict:
    """Valida todos os dados com Pydantic. Rejeita registros inválidos."""
    logger.info("[LangGraph] Validando dados com Pydantic...")
    focos_validados = []
    erros = []

    for item in estado.get("focos_brutos", []):
        try:
            foco = FocoQueimada(**item)
            focos_validados.append(foco)
        except Exception as e:
            erros.append(f"Foco inválido: {e}")

    dados_clima_validados = []
    for item in estado.get("dados_climaticos", []):
        try:
            dado = DadoClimatico(**item)
            dados_clima_validados.append(dado)
        except Exception as e:
            erros.append(f"Dado climático inválido: {e}")

    logger.info(
        "[LangGraph] Validados: %d focos, %d clima | Erros: %d",
        len(focos_validados), len(dados_clima_validados), len(erros),
    )
    return {
        "focos_validados": focos_validados,
        "dados_climaticos_validados": dados_clima_validados,
        "erros": erros,
    }


async def no_agente_geoespacial(estado: EstadoPipeline) -> dict:
    """Cruza focos com municípios, UCs e áreas sensíveis via PostGIS."""
    logger.info("[LangGraph] Agente Geoespacial: cruzando focos...")
    from app.core.database import AsyncSessionLocal
    from app.services.geo_service import enriquecer_foco

    focos_enriquecidos = []
    async with AsyncSessionLocal() as db:
        for foco in estado.get("focos_validados", []):
            try:
                foco_enriquecido = await enriquecer_foco(foco, db)
                focos_enriquecidos.append(foco_enriquecido.model_dump())
            except Exception as e:
                logger.warning("Erro ao enriquecer foco: %s", e)
                focos_enriquecidos.append(foco.model_dump())

    return {"focos_enriquecidos": focos_enriquecidos}


async def no_agente_goes16(estado: EstadoPipeline) -> dict:
    """Analisa dados GOES-16: persistência, FRP, temperatura e evolução."""
    logger.info("[LangGraph] Agente GOES-16: analisando...")
    from app.services.goes16_service import coletar_dados_goes16

    leituras = await coletar_dados_goes16(horas_atras=2)
    leituras_validadas = []
    for l in leituras:
        try:
            leituras_validadas.append(LeituraGOES16(**l.model_dump()))
        except Exception:
            pass

    # Análise de persistência
    focos_persistentes = [l for l in leituras_validadas if (l.deteccoes_consecutivas or 0) >= 3]
    frp_total = sum(l.frp_mw or 0 for l in leituras_validadas)
    temp_max = max((l.temperatura_pixel_k or 0 for l in leituras_validadas), default=0)

    analise = {
        "total_pixels_fogo": len(leituras_validadas),
        "focos_persistentes": len(focos_persistentes),
        "frp_total_mw": round(frp_total, 2),
        "temperatura_max_k": round(temp_max, 2),
        "municipios_afetados": list({l.municipio for l in leituras_validadas if l.municipio}),
    }

    return {
        "leituras_goes16_validadas": leituras_validadas,
        "analise_goes16": analise,
    }


async def no_agente_climatico(estado: EstadoPipeline) -> dict:
    """Calcula risco climático: seca, umidade, vento, temperatura."""
    logger.info("[LangGraph] Agente Climático: calculando risco...")
    dados = estado.get("dados_climaticos_validados", [])

    if not dados:
        return {"analise_climatica": {"status": "sem_dados"}}

    # Agrega por município
    por_municipio: dict[str, list] = {}
    for d in dados:
        por_municipio.setdefault(d.municipio, []).append(d)

    analise_municipios = {}
    for municipio, leituras in por_municipio.items():
        umidade_media = _media([l.umidade_relativa for l in leituras if l.umidade_relativa])
        vento_medio = _media([l.velocidade_vento_ms for l in leituras if l.velocidade_vento_ms])
        dias_seca = max((l.dias_sem_chuva or 0 for l in leituras), default=0)
        temp_media = _media([l.temperatura_c for l in leituras if l.temperatura_c])

        risco_climatico = _calcular_risco_climatico(umidade_media, vento_medio, dias_seca)

        analise_municipios[municipio] = {
            "umidade_media": umidade_media,
            "vento_medio_ms": vento_medio,
            "dias_sem_chuva": dias_seca,
            "temperatura_media": temp_media,
            "risco_climatico": risco_climatico,
        }

    return {"analise_climatica": analise_municipios}


async def no_fundir_evidencias(estado: EstadoPipeline) -> dict:
    """Funde evidências de todas as fontes para cada município."""
    logger.info("[LangGraph] Fundindo evidências...")
    focos = estado.get("focos_enriquecidos", [])
    analise_goes = estado.get("analise_goes16", {})
    analise_clima = estado.get("analise_climatica", {})

    # Agrupa focos por município
    por_municipio: dict[str, list] = {}
    for f in focos:
        mun = f.get("municipio") or "Desconhecido"
        por_municipio.setdefault(mun, []).append(f)

    evidencias: dict[str, dict] = {}
    for municipio, focos_mun in por_municipio.items():
        clima = analise_clima.get(municipio, {})
        evidencias[municipio] = {
            "total_focos": len(focos_mun),
            "fontes": list({f["fonte"] for f in focos_mun}),
            "frp_total": sum(f.get("frp") or 0 for f in focos_mun),
            "goes16_confirmado": municipio in analise_goes.get("municipios_afetados", []),
            "risco_climatico": clima.get("risco_climatico", 0),
            "dias_sem_chuva": clima.get("dias_sem_chuva", 0),
            "umidade_media": clima.get("umidade_media"),
        }

    return {"evidencias_fundidas": evidencias}


async def no_classificar_risco(estado: EstadoPipeline) -> dict:
    """Classifica risco por município e consolida eventos."""
    logger.info("[LangGraph] Classificando risco...")
    evidencias = estado.get("evidencias_fundidas", {})
    eventos = []
    riscos = []

    for municipio, ev in evidencias.items():
        # Calcular índice de risco
        indice = _calcular_indice_risco(ev)
        classificacao = _classificar(indice)

        # Criar evento consolidado se houver focos
        if ev["total_focos"] > 0:
            evento = EventoQueimada(
                municipio=municipio,
                latitude_centroide=-5.0,  # placeholder — em produção usa centroide real
                longitude_centroide=-39.0,
                fontes=ev["fontes"],
                inicio=datetime.utcnow(),
                ultima_deteccao=datetime.utcnow(),
                quantidade_focos=ev["total_focos"],
                severidade=classificacao,
                confianca=min(ev["total_focos"] * 10, 95),
                goes16_confirmado=ev["goes16_confirmado"],
                justificativa=_gerar_justificativa(municipio, ev, indice),
            )
            eventos.append(evento)

        risco = RiscoMunicipal(
            municipio=municipio,
            codigo_ibge="",
            data_calculo=datetime.utcnow(),
            indice_risco=indice,
            classificacao=classificacao,
            focos_24h=ev["total_focos"],
            dias_sem_chuva=ev.get("dias_sem_chuva"),
            umidade_media=ev.get("umidade_media"),
            justificativa=_gerar_justificativa(municipio, ev, indice),
        )
        riscos.append(risco)

    return {
        "eventos_consolidados": eventos,
        "riscos_municipais": riscos,
    }


async def no_agente_react_diagnostico(estado: EstadoPipeline) -> dict:
    """Agente ReAct que raciocina sobre os eventos e produz diagnóstico."""
    logger.info("[LangGraph] Agente ReAct: diagnóstico...")
    eventos = estado.get("eventos_consolidados", [])

    if not eventos:
        return {"diagnostico": "Nenhum evento de queimada detectado no período."}

    criticos = [e for e in eventos if e.severidade in ("alta", "critica")]
    resumo = (
        f"Detectados {len(eventos)} eventos de queimada no Ceará. "
        f"{len(criticos)} com severidade alta ou crítica. "
        f"Municípios afetados: {', '.join(e.municipio for e in eventos[:5])}."
    )

    # Em produção, chama o agente ReAct completo
    # from app.agents.react_agent import diagnosticar
    # resposta = await diagnosticar(f"Analise os seguintes eventos: {resumo}")

    return {"diagnostico": resumo}


async def no_gerar_alertas(estado: EstadoPipeline) -> dict:
    """Gera alertas para eventos críticos e de alta severidade."""
    logger.info("[LangGraph] Gerando alertas...")
    eventos = estado.get("eventos_consolidados", [])
    alertas = []

    for evento in eventos:
        if evento.severidade in ("alta", "critica"):
            nivel = "emergencia" if evento.severidade == "critica" else "alerta"
            alerta = AlertaQueimada(
                evento_id=evento.id_evento,
                nivel=nivel,
                municipio=evento.municipio,
                mensagem=(
                    f"Queimada {evento.severidade.upper()} detectada em {evento.municipio}. "
                    f"{evento.quantidade_focos} focos confirmados. "
                    f"Fontes: {', '.join(evento.fontes)}."
                ),
                recomendacao=_gerar_recomendacao(evento),
                fontes_evidencia=evento.fontes,
                agente_responsavel="AgentAlerta",
                nivel_confianca=evento.confianca / 100,
                justificativa_tecnica=evento.justificativa,
            )
            alertas.append(alerta)

    logger.info("[LangGraph] %d alertas gerados", len(alertas))
    return {"alertas": alertas}


async def no_gerar_boletim(estado: EstadoPipeline) -> dict:
    """Gera boletim técnico consolidado."""
    logger.info("[LangGraph] Gerando boletim...")
    eventos = estado.get("eventos_consolidados", [])
    alertas = estado.get("alertas", [])
    diagnostico = estado.get("diagnostico", "")

    boletim = (
        f"BOLETIM DE QUEIMADAS — CEARÁ\n"
        f"Data/Hora: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC\n\n"
        f"RESUMO EXECUTIVO\n{diagnostico}\n\n"
        f"EVENTOS DETECTADOS: {len(eventos)}\n"
        f"ALERTAS EMITIDOS: {len(alertas)}\n\n"
        f"MUNICÍPIOS CRÍTICOS:\n"
    )
    criticos = [e for e in eventos if e.severidade in ("alta", "critica")]
    for e in criticos[:10]:
        boletim += f"  - {e.municipio}: {e.severidade.upper()} ({e.quantidade_focos} focos)\n"

    return {"boletim": boletim}


# ---------------------------------------------------------------------------
# Construção do grafo LangGraph
# ---------------------------------------------------------------------------

def construir_grafo() -> StateGraph:
    """Constrói e retorna o grafo LangGraph completo."""
    grafo = StateGraph(EstadoPipeline)

    # Adiciona nós
    grafo.add_node("coletar_dados", no_coletar_dados)
    grafo.add_node("validar_dados", no_validar_dados)
    grafo.add_node("agente_geoespacial", no_agente_geoespacial)
    grafo.add_node("agente_goes16", no_agente_goes16)
    grafo.add_node("agente_climatico", no_agente_climatico)
    grafo.add_node("fundir_evidencias", no_fundir_evidencias)
    grafo.add_node("classificar_risco", no_classificar_risco)
    grafo.add_node("agente_react_diagnostico", no_agente_react_diagnostico)
    grafo.add_node("gerar_alertas", no_gerar_alertas)
    grafo.add_node("gerar_boletim", no_gerar_boletim)

    # Define fluxo
    grafo.add_edge(START, "coletar_dados")
    grafo.add_edge("coletar_dados", "validar_dados")
    grafo.add_edge("validar_dados", "agente_geoespacial")
    grafo.add_edge("validar_dados", "agente_goes16")
    grafo.add_edge("validar_dados", "agente_climatico")
    grafo.add_edge("agente_geoespacial", "fundir_evidencias")
    grafo.add_edge("agente_goes16", "fundir_evidencias")
    grafo.add_edge("agente_climatico", "fundir_evidencias")
    grafo.add_edge("fundir_evidencias", "classificar_risco")
    grafo.add_edge("classificar_risco", "agente_react_diagnostico")
    grafo.add_edge("agente_react_diagnostico", "gerar_alertas")
    grafo.add_edge("gerar_alertas", "gerar_boletim")
    grafo.add_edge("gerar_boletim", END)

    return grafo.compile()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _media(valores: list) -> float | None:
    vals = [v for v in valores if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _calcular_risco_climatico(umidade, vento, dias_seca) -> float:
    score = 0.0
    if umidade is not None:
        score += max(0, (50 - umidade) * 0.4)
    if vento is not None:
        score += min(vento * 1.5, 20)
    if dias_seca:
        score += min(dias_seca * 1.5, 30)
    return round(min(score, 100), 1)


def _calcular_indice_risco(ev: dict) -> float:
    score = min(ev.get("total_focos", 0) * 8, 40)
    score += ev.get("risco_climatico", 0) * 0.4
    if ev.get("goes16_confirmado"):
        score += 15
    frp = ev.get("frp_total", 0)
    score += min(frp / 100, 10)
    return round(min(score, 100), 1)


def _classificar(indice: float) -> str:
    if indice >= 75:
        return "critica"
    if indice >= 50:
        return "alta"
    if indice >= 25:
        return "media"
    return "baixa"


def _gerar_justificativa(municipio: str, ev: dict, indice: float) -> str:
    partes = [f"Município {municipio} com índice de risco {indice:.1f}/100."]
    if ev.get("total_focos"):
        partes.append(f"{ev['total_focos']} focos detectados nas últimas 24h.")
    if ev.get("goes16_confirmado"):
        partes.append("GOES-16 confirmou presença de fogo.")
    if ev.get("dias_sem_chuva"):
        partes.append(f"{ev['dias_sem_chuva']} dias sem chuva.")
    if ev.get("umidade_media") and ev["umidade_media"] < 40:
        partes.append(f"Umidade relativa baixa ({ev['umidade_media']:.0f}%).")
    return " ".join(partes)


def _gerar_recomendacao(evento: EventoQueimada) -> str:
    if evento.severidade == "critica":
        return (
            "AÇÃO IMEDIATA: Acionar Defesa Civil e Corpo de Bombeiros. "
            "Evacuar áreas de risco. Monitorar evolução a cada 30 minutos."
        )
    return (
        "Monitorar evolução do foco. Alertar equipes de campo. "
        "Verificar condições de acesso viário."
    )
