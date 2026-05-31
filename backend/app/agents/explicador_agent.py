"""
Agente Explicador de Focos de Queimada.
Para cada foco real detectado, o agente busca dados climáticos reais
e gera uma explicação técnica detalhada usando LangChain + OpenAI.

Funciona SEM banco de dados — consulta APIs externas diretamente.
"""

import json
import logging
from datetime import datetime

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.clima_real import buscar_clima_foco

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ferramenta: buscar clima real para coordenada do foco
# ---------------------------------------------------------------------------

class BuscarClimaFocoInput(BaseModel):
    lat: float = Field(..., description="Latitude do foco")
    lon: float = Field(..., description="Longitude do foco")


class BuscarClimaFocoTool(BaseTool):
    name: str = "buscar_clima_foco"
    description: str = (
        "Busca dados climáticos REAIS e ATUAIS para a coordenada exata de um foco de queimada. "
        "Retorna temperatura, umidade relativa, velocidade do vento, precipitação e dias sem chuva. "
        "Use esta ferramenta para entender as condições que favorecem ou desfavorecem o fogo."
    )
    args_schema: type[BaseModel] = BuscarClimaFocoInput

    def _run(self, lat: float, lon: float) -> str:
        return json.dumps({"erro": "use _arun"})

    async def _arun(self, lat: float, lon: float) -> str:
        clima = await buscar_clima_foco(lat, lon)
        if not clima:
            return json.dumps({"erro": "Dados climáticos não disponíveis"})
        return json.dumps(clima, ensure_ascii=False)


class AnalisarFocoInput(BaseModel):
    frp: float = Field(..., description="Fire Radiative Power em MW")
    temperatura_k: float = Field(..., description="Temperatura do pixel em Kelvin")
    confianca: float = Field(..., description="Confiança da detecção em %")
    sensor: str = Field(..., description="Sensor que detectou (VIIRS ou MODIS)")


class AnalisarIntensidadeTool(BaseTool):
    name: str = "analisar_intensidade_foco"
    description: str = (
        "Analisa a intensidade de um foco com base no FRP (Fire Radiative Power), "
        "temperatura do pixel e confiança da detecção. "
        "Retorna classificação de intensidade e interpretação técnica."
    )
    args_schema: type[BaseModel] = AnalisarFocoInput

    def _run(self, frp: float, temperatura_k: float, confianca: float, sensor: str) -> str:
        temp_c = temperatura_k - 273.15 if temperatura_k > 200 else temperatura_k

        if frp >= 50:
            intensidade = "MUITO ALTA"
            descricao = "Fogo de grande porte com alta liberação de energia radiativa"
        elif frp >= 15:
            intensidade = "ALTA"
            descricao = "Fogo ativo e intenso, possivelmente em expansão"
        elif frp >= 5:
            intensidade = "MODERADA"
            descricao = "Fogo ativo de intensidade moderada"
        else:
            intensidade = "BAIXA"
            descricao = "Foco de baixa intensidade, possivelmente em início ou extinção"

        confianca_texto = "alta" if confianca >= 80 else "moderada" if confianca >= 50 else "baixa"

        return json.dumps({
            "intensidade": intensidade,
            "descricao": descricao,
            "frp_mw": frp,
            "temperatura_celsius": round(temp_c, 1),
            "confianca_deteccao": f"{confianca:.0f}% ({confianca_texto})",
            "sensor": sensor,
            "interpretacao": (
                f"O sensor {sensor} detectou este foco com FRP de {frp:.1f} MW "
                f"e temperatura de {temp_c:.1f}°C. "
                f"Intensidade classificada como {intensidade}."
            ),
        }, ensure_ascii=False)

    async def _arun(self, frp: float, temperatura_k: float, confianca: float, sensor: str) -> str:
        return self._run(frp, temperatura_k, confianca, sensor)


# ---------------------------------------------------------------------------
# Prompt do agente explicador
# ---------------------------------------------------------------------------

EXPLICADOR_PROMPT = """Você é um especialista em análise de queimadas no Estado do Ceará, Brasil.
Sua função é explicar, de forma técnica e clara, POR QUE um foco de queimada foi detectado
e quais fatores climáticos e ambientais contribuem para o risco.

Você tem acesso a ferramentas que consultam dados REAIS e ATUAIS.
SEMPRE use as ferramentas antes de responder. Não invente dados.

Ferramentas disponíveis:
{tools}

Nomes das ferramentas: {tool_names}

Use o formato OBRIGATÓRIO:
Pensamento: o que preciso verificar
Ação: nome_da_ferramenta
Entrada da Ação: {{"parametro": valor}}
Observação: resultado da ferramenta
... (repita conforme necessário)
Pensamento: Tenho dados suficientes para explicar
Resposta Final: [explicação estruturada]

Foco para analisar:
{input}
{agent_scratchpad}"""

PROMPT_TEMPLATE = PromptTemplate.from_template(EXPLICADOR_PROMPT)


def _criar_agente_explicador() -> AgentExecutor:
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.1,
        api_key=settings.OPENAI_API_KEY,
    )
    tools = [BuscarClimaFocoTool(), AnalisarIntensidadeTool()]
    agent = create_react_agent(llm=llm, tools=tools, prompt=PROMPT_TEMPLATE)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


async def explicar_foco(foco: dict) -> dict:
    """
    Usa o agente ReAct para explicar um foco de queimada real.
    Consulta clima real e analisa intensidade.
    Retorna dict com explicação, evidências e recomendação.
    """
    executor = _criar_agente_explicador()

    descricao = (
        f"Foco detectado em {foco.get('municipio') or 'Ceará'} "
        f"(lat={foco['lat']:.4f}, lon={foco['lon']:.4f})\n"
        f"Satélite/Sensor: {foco.get('satelite', 'N/A')} / {foco.get('sensor', 'N/A')}\n"
        f"Data/Hora: {foco.get('data_hora', 'N/A')}\n"
        f"FRP: {foco.get('frp') or 'N/A'} MW\n"
        f"Temperatura do pixel: {foco.get('temperatura_k') or 'N/A'} K\n"
        f"Confiança: {foco.get('confianca') or 'N/A'}%\n"
        f"Severidade: {foco.get('severidade', 'N/A')}\n\n"
        f"Explique por que este foco foi detectado, quais condições climáticas "
        f"favorecem ou desfavorecem o fogo neste local, e qual a recomendação operacional."
    )

    try:
        resultado = await executor.ainvoke({"input": descricao})
    except Exception as e:
        logger.error("Erro no agente explicador: %s", e)
        # Fallback: explicação sem LLM usando apenas dados climáticos
        return await _explicar_sem_llm(foco)

    passos = []
    ferramentas = []
    evidencias = []
    clima_dados = {}

    for step in resultado.get("intermediate_steps", []):
        action, obs = step
        passos.append(f"{action.tool}: {str(obs)[:150]}")
        ferramentas.append(action.tool)
        if "clima" in action.tool:
            try:
                clima_dados = json.loads(obs) if isinstance(obs, str) else obs
            except Exception:
                pass
        evidencias.append(str(obs)[:200])

    return {
        "foco_id": foco.get("id"),
        "explicacao": resultado.get("output", ""),
        "clima": clima_dados,
        "ferramentas_usadas": list(set(ferramentas)),
        "evidencias": evidencias,
        "passos_raciocinio": passos,
        "nivel_confianca": 0.9 if ferramentas else 0.5,
        "gerado_em": datetime.utcnow().isoformat(),
    }


async def _explicar_sem_llm(foco: dict) -> dict:
    """Fallback: gera explicação baseada em regras quando LLM não está disponível."""
    clima = await buscar_clima_foco(foco["lat"], foco["lon"])

    partes = []
    frp = foco.get("frp") or 0
    temp_k = foco.get("temperatura_k") or 0
    confianca = foco.get("confianca") or 0

    # Intensidade
    if frp >= 15:
        partes.append(f"Foco de alta intensidade com FRP de {frp:.1f} MW detectado pelo {foco.get('sensor', 'satélite')}.")
    elif frp >= 5:
        partes.append(f"Foco de intensidade moderada com FRP de {frp:.1f} MW.")
    else:
        partes.append(f"Foco de baixa intensidade detectado pelo {foco.get('sensor', 'satélite')}.")

    # Clima
    if clima:
        umidade = clima.get("umidade_relativa")
        vento = clima.get("velocidade_vento_ms")
        dias_seca = clima.get("dias_sem_chuva", 0)
        temp_c = clima.get("temperatura_c")

        if umidade and umidade < 40:
            partes.append(f"Umidade relativa muito baixa ({umidade:.0f}%) favorece a propagação do fogo.")
        elif umidade and umidade < 60:
            partes.append(f"Umidade relativa baixa ({umidade:.0f}%) contribui para o risco.")

        if dias_seca and dias_seca >= 10:
            partes.append(f"Região com {dias_seca} dias sem chuva — vegetação seca e altamente inflamável.")
        elif dias_seca and dias_seca >= 5:
            partes.append(f"{dias_seca} dias sem precipitação significativa.")

        if vento and vento >= 5:
            partes.append(f"Vento de {vento:.1f} m/s pode acelerar a propagação.")

        if temp_c and temp_c >= 35:
            partes.append(f"Temperatura elevada ({temp_c:.1f}°C) aumenta o risco de ignição.")

    if confianca >= 80:
        partes.append(f"Detecção com alta confiança ({confianca:.0f}%).")

    explicacao = " ".join(partes) if partes else "Foco detectado por satélite no Ceará."

    return {
        "foco_id": foco.get("id"),
        "explicacao": explicacao,
        "clima": clima,
        "ferramentas_usadas": ["buscar_clima_foco"],
        "evidencias": [f"Clima: {json.dumps(clima, ensure_ascii=False)}"],
        "passos_raciocinio": ["Análise baseada em regras (LLM indisponível)"],
        "nivel_confianca": 0.7,
        "gerado_em": datetime.utcnow().isoformat(),
    }
