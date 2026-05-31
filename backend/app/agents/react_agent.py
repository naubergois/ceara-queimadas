"""
Agente ReAct de Diagnóstico de Queimadas.
Usa LangChain + padrão ReAct para raciocinar sobre focos, clima e risco,
consultando ferramentas reais e produzindo recomendações operacionais.
"""

import logging
from datetime import datetime

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.models.schemas import RespostaAgente
from app.tools.queimada_tools import get_all_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt ReAct em português
# ---------------------------------------------------------------------------

REACT_PROMPT_TEMPLATE = """Você é um especialista em monitoramento de queimadas no Estado do Ceará, Brasil.
Você tem acesso a ferramentas que consultam dados reais de satélite, clima e território.

Seu objetivo é responder perguntas operacionais sobre queimadas com base em evidências concretas.
Sempre consulte as ferramentas disponíveis antes de responder.
Estruture sua resposta final com: resumo, evidências, fontes, nível de confiança e recomendação operacional.

Ferramentas disponíveis:
{tools}

Nomes das ferramentas: {tool_names}

Use o seguinte formato OBRIGATÓRIO:

Pergunta: a pergunta que você deve responder
Pensamento: raciocine sobre o que precisa fazer
Ação: nome_da_ferramenta
Entrada da Ação: parâmetros da ferramenta em JSON
Observação: resultado da ferramenta
... (repita Pensamento/Ação/Entrada/Observação quantas vezes necessário)
Pensamento: Agora tenho informações suficientes para responder
Resposta Final: [resposta estruturada com resumo, evidências, fontes, confiança e recomendação]

Pergunta: {input}
{agent_scratchpad}"""

REACT_PROMPT = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)


def criar_agente_react() -> AgentExecutor:
    """Cria e retorna o AgentExecutor ReAct configurado."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )
    tools = get_all_tools()
    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=8,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )
    return executor


async def diagnosticar(pergunta: str) -> RespostaAgente:
    """
    Executa o agente ReAct para responder uma pergunta operacional.
    Retorna RespostaAgente com evidências, fontes e recomendação.
    """
    executor = criar_agente_react()

    try:
        resultado = await executor.ainvoke({"input": pergunta})
    except Exception as e:
        logger.error("Erro no agente ReAct: %s", e)
        return RespostaAgente(
            pergunta=pergunta,
            resposta=f"Erro ao processar: {e}",
            resumo="Falha na execução do agente",
            nivel_confianca=0.0,
        )

    # Extrair passos intermediários
    passos = []
    ferramentas_usadas = []
    evidencias = []

    for step in resultado.get("intermediate_steps", []):
        action, observation = step
        passos.append(f"Ação: {action.tool} | Entrada: {action.tool_input}")
        ferramentas_usadas.append(action.tool)
        evidencias.append(f"[{action.tool}]: {str(observation)[:200]}")

    resposta_texto = resultado.get("output", "")

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
