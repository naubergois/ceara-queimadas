"""
Agente Auditor de Evidências.
Verifica se um alerta foi gerado com base em evidências suficientes,
detecta possíveis falsos positivos e emite parecer técnico.
"""

import logging
from datetime import datetime

from langchain.agents import create_agent
from app.agents.llm_factory import create_chat_llm
from app.models.schemas import AlertaQueimada, AuditoriaAlerta
from app.tools.queimada_tools import (
    BuscarDadosGOES16Tool,
    BuscarDadosClimaticosToool,
    BuscarFocosRecentesTool,
    BuscarHistoricoMapBiomasTool,
)

logger = logging.getLogger(__name__)

AUDITOR_SYSTEM_PROMPT = """Você é um auditor técnico especializado em validação de alertas de queimadas no Ceará.
Sua função é verificar se um alerta emitido é justificável com base nas evidências disponíveis.

Você deve responder às seguintes perguntas:
1. Este alerta é justificável?
2. Quais fontes confirmam o evento?
3. Há divergência entre GOES-16, INPE e NASA FIRMS?
4. O alerta pode ser um falso positivo?
5. Qual dado climático reforça ou enfraquece o risco?

Use o formato:
Pensamento: raciocine sobre o alerta
Ação: ferramenta
Entrada da Ação: parâmetros JSON
Observação: resultado
... (repita conforme necessário)
Pensamento: Tenho evidências suficientes para emitir parecer
Resposta Final: [parecer estruturado com justificativa, fontes, divergências e nível de confiança]"""


def criar_agente_auditor():
    llm = create_chat_llm(temperature=0)
    tools = [
        BuscarFocosRecentesTool(),
        BuscarDadosGOES16Tool(),
        BuscarDadosClimaticosToool(),
        BuscarHistoricoMapBiomasTool(),
    ]
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=AUDITOR_SYSTEM_PROMPT,
    )


async def auditar_alerta(alerta: AlertaQueimada) -> AuditoriaAlerta:
    """
    Executa auditoria completa de um alerta.
    Retorna AuditoriaAlerta com parecer técnico.
    """
    agent = criar_agente_auditor()

    descricao_alerta = (
        f"Alerta ID: {alerta.id_alerta}\n"
        f"Município: {alerta.municipio}\n"
        f"Nível: {alerta.nivel}\n"
        f"Mensagem: {alerta.mensagem}\n"
        f"Fontes de evidência: {', '.join(alerta.fontes_evidencia)}\n"
        f"Confiança declarada: {alerta.nivel_confianca:.0%}\n"
        f"Justificativa técnica: {alerta.justificativa_tecnica}"
    )

    try:
        resultado = await agent.ainvoke({"messages": [("human", descricao_alerta)]})
    except Exception as e:
        logger.error("Erro no agente auditor: %s", e)
        return AuditoriaAlerta(
            alerta_id=alerta.id_alerta,
            justificavel=False,
            parecer=f"Erro na auditoria: {e}",
            confianca_auditoria=0.0,
        )

    mensagens = resultado.get("messages", [])
    parecer = ""
    for msg in reversed(mensagens):
        if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
            parecer = msg.content or ""
            if parecer:
                break

    fontes_confirmam = []
    divergencias = []
    for msg in mensagens:
        if hasattr(msg, "type") and msg.type == "tool":
            obs = str(msg.content or "")
            if "fogo" in obs.lower():
                fontes_confirmam.append(msg.name or "tool")
        if hasattr(msg, "type") and msg.type == "ai":
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    nome = tc.get("name", "")
                    if "goes16" in nome.lower():
                        fontes_confirmam.append("GOES-16")
                    if "foco" in nome.lower():
                        fontes_confirmam.append("INPE/FIRMS")

    justificavel = len(fontes_confirmam) >= 1
    suspeita_fp = "falso positivo" in parecer.lower() or len(fontes_confirmam) == 0

    return AuditoriaAlerta(
        alerta_id=alerta.id_alerta,
        justificavel=justificavel,
        fontes_confirmam=list(set(fontes_confirmam)),
        divergencias=divergencias,
        suspeita_falso_positivo=suspeita_fp,
        parecer=parecer,
        confianca_auditoria=0.9 if justificavel else 0.4,
    )
