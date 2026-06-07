"""Agente ReAct de Diagnóstico de Queimadas.
Usa LangChain (v1.3+) + padrão ReAct para raciocinar sobre focos, clima e risco,
consultando ferramentas reais e produzindo recomendações operacionais.
"""

import logging
from datetime import datetime

from langchain.agents import create_agent
from app.agents.llm_factory import create_chat_llm
from app.models.schemas import RespostaAgente
from app.tools.queimada_tools import get_all_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt ReAct em português (system prompt — langchain 1.3+ usa system_prompt)
# ---------------------------------------------------------------------------

REACT_SYSTEM_PROMPT = """Você é um especialista em monitoramento de queimadas no Estado do Ceará, Brasil.
Você tem acesso a ferramentas que consultam dados reais de satélite, clima e território.

Seu objetivo é responder perguntas operacionais sobre queimadas com base em evidências concretas.
Sempre consulte as ferramentas disponíveis antes de responder.
Estruture sua resposta final com: resumo, evidências, fontes, nível de confiança e recomendação operacional.

Use o seguinte formato OBRIGATÓRIO:

Pergunta: a pergunta que você deve responder
Pensamento: raciocine sobre o que precisa fazer
Ação: nome_da_ferramenta
Entrada da Ação: parâmetros da ferramenta em JSON
Observação: resultado da ferramenta
... (repita Pensamento/Ação/Entrada/Observação quantas vezes necessário)
Pensamento: Agora tenho informações suficientes para responder
Resposta Final: [resposta estruturada com resumo, evidências, fontes, confiança e recomendação]"""


def criar_agente_react():
    """Cria e retorna o CompiledStateGraph ReAct configurado (langchain 1.3+)."""
    llm = create_chat_llm(temperature=0)
    tools = get_all_tools()
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=REACT_SYSTEM_PROMPT,
    )
    return agent


async def diagnosticar(pergunta: str) -> RespostaAgente:
    """
    Executa o agente ReAct para responder uma pergunta operacional.
    Retorna RespostaAgente com evidências, fontes e recomendação.
    """
    agent = criar_agente_react()

    try:
        # API langchain 1.3+: invoca com messages, retorna {messages: [...]}
        resultado = await agent.ainvoke({"messages": [("human", pergunta)]})
    except Exception as e:
        logger.error("Erro no agente ReAct: %s", e)
        return RespostaAgente(
            pergunta=pergunta,
            resposta=f"Erro ao processar: {e}",
            resumo="Falha na execução do agente",
            nivel_confianca=0.0,
        )

    # Extrair resposta das mensagens
    mensagens = resultado.get("messages", [])
    resposta_texto = ""
    for msg in reversed(mensagens):
        if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
            resposta_texto = msg.content or ""
            if resposta_texto:
                break

    # Ferramentas usadas a partir dos tool calls nas mensagens
    ferramentas_usadas = []
    evidencias = []
    passos = []
    for msg in mensagens:
        if hasattr(msg, "type") and msg.type == "ai":
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    nome = tc.get("name", "?")
                    ferramentas_usadas.append(nome)
                    passos.append(f"Ação: {nome} | Entrada: {tc.get('args', {})}")
        if hasattr(msg, "type") and msg.type == "tool":
            evidencias.append(f"[{msg.name or 'tool'}]: {str(msg.content)[:200]}")

    return RespostaAgente(
        pergunta=pergunta,
        resposta=resposta_texto,
        resumo=resposta_texto[:300],
        evidencias=evidencias,
        fontes=list(set(ferramentas_usadas)),
        data_hora_consulta=datetime.utcnow(),
        nivel_confianca=0.85 if ferramentas_usadas else 0.3,
        recomendacao_operacional=_extrair_recomendacao(resposta_texto),
        ferramentas_usadas=ferramentas_usadas,
        passos_raciocinio=passos,
    )


def _extrair_recomendacao(texto: str) -> str:
    """Extrai a recomendação operacional do texto de resposta."""
    linhas = texto.split("\n")
    for i, linha in enumerate(linhas):
        if "recomend" in linha.lower():
            return "\n".join(linhas[i : i + 3]).strip()
    return ""
