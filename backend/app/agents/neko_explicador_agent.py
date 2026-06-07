"""
INOV-009: Agente Explicador ReAct NeKo-PIGNN (DeepSeek + SHAP)
===============================================================
Agente LangChain criado com create_agent() (LangChain 1.3+)
que explica previsões do modelo NeKo-PIGNN em linguagem natural.

Tools:
1. buscar_clima_foco — clima real via Open-Meteo
2. analisar_intensidade_foco — classificação FRP
3. analisar_risco_koopman — risco via Neural Koopman Operator
4. simulacao_causal — intervenções "e se..."
5. analisar_features_shap — importância de features via gradientes

Usa DeepSeek como LLM (via llm_factory.py).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch

from langchain.agents import create_agent
from langchain_core.tools import tool

from app.agents.llm_factory import create_chat_llm

logger = logging.getLogger(__name__)

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_cache: dict[str, torch.nn.Module] = {}

# ---------------------------------------------------------------------------
# Tools @tool decorator (LangChain 1.3+)
# ---------------------------------------------------------------------------


@tool
def buscar_clima_foco(lat: float, lon: float) -> str:
    """Busca dados climáticos REAIS para coordenada de um foco via Open-Meteo.
    Retorna temperatura, umidade, vento, precipitação e dias sem chuva.
    """
    import asyncio
    from app.services.clima_real import buscar_clima_por_coordenada
    try:
        loop = asyncio.get_running_loop()
        clima = loop.run_until_complete(buscar_clima_por_coordenada(lat, lon))
    except RuntimeError:
        clima = asyncio.run(buscar_clima_por_coordenada(lat, lon))
    return json.dumps(clima or {"erro": "Dados climáticos não disponíveis"}, ensure_ascii=False)


@tool
def analisar_intensidade_foco(frp: float, temperatura_k: float, confianca: float, sensor: str) -> str:
    """Classifica a intensidade de um foco com base em FRP (MW), temperatura (K) e confiança (%)."""
    temp_c = temperatura_k - 273.15 if temperatura_k > 200 else temperatura_k
    intensidade = "MUITO ALTA" if frp >= 50 else "ALTA" if frp >= 15 else "MODERADA" if frp >= 5 else "BAIXA"
    conf_txt = "alta" if confianca >= 80 else "moderada" if confianca >= 50 else "baixa"
    return json.dumps({
        "intensidade": intensidade, "frp_mw": frp,
        "temperatura_celsius": round(temp_c, 1),
        "confianca": f"{confianca:.0f}% ({conf_txt})", "sensor": sensor,
    }, ensure_ascii=False)


@tool
def analisar_risco_koopman(municipios_json: str, features_json: str) -> str:
    """Analisa risco de queimadas usando Neural Koopman Operator.
    municipios_json: lista JSON de nomes de municípios
    features_json: lista JSON de arrays de features [[temp,frp,vento,umidade,ndvi,declividade], ...]
    Retorna modos coerentes + projeção de risco.
    """
    municipios = json.loads(municipios_json)
    features = json.loads(features_json)
    x = torch.tensor(features, dtype=torch.float32, device=_device)

    from app.models.inovacao.koopman_operator import NeuralKoopmanOperator
    if "koopman" not in _model_cache:
        m = NeuralKoopmanOperator(input_dim=6, latent_dim=32, koopman_rank=16).to(_device).eval()
        _model_cache["koopman"] = m
    model = _model_cache["koopman"]

    with torch.no_grad():
        _, _, z = model.encode(x)
        z_future = model.forward_koopman(z, steps=6)
        x_pred = model.decode(z_future)
        K = model.K_matrix.detach().cpu().numpy()
        eigvals = np.linalg.eigvals(K)

    risco = float(torch.sigmoid(z.mean()).item())
    dominancia = float(np.max(np.abs(eigvals))) / float(np.sum(np.abs(eigvals)) + 1e-10)
    top3_idx = torch.topk(z.mean(dim=1), min(3, z.shape[0])).indices.cpu().tolist()

    return json.dumps({
        "risco_global": round(risco, 3),
        "dominancia_modo1": round(dominancia, 3),
        "municipios_maior_risco": [municipios[i] for i in top3_idx],
        "modos_coerentes": [float(np.abs(e)) for e in sorted(eigvals, key=np.abs, reverse=True)[:5]],
        "interpretacao": (
            f"Risco estimado: {risco:.1%}. Modo-1 concentra {dominancia:.1%} da dinâmica. "
            f"{'Alerta: dinâmica dominante muito forte' if dominancia > 0.5 else 'Dinâmica distribuída em múltiplos modos'}"
        ),
    }, ensure_ascii=False)


@tool
def simulacao_causal(municipio: str, features_atual_json: str, intervencao_json: str) -> str:
    """Simula intervenção causal 'e se...' no modelo NeKo-PIGNN.
    features_atual_json: features atuais [temp,frp,vento,umidade,ndvi,declividade]
    intervencao_json: dict com variáveis e novos valores {"vento": 0.8, "umidade": 0.3}
    Retorna como o risco muda com a intervenção.
    """
    features = np.array(json.loads(features_atual_json), dtype=np.float32)
    intervencao = json.loads(intervencao_json)
    var_map = {"temp": 0, "frp": 1, "vento": 2, "umidade": 3, "ndvi": 4, "declividade": 5}

    features_interv = features.copy()
    for var, val in intervencao.items():
        idx = var_map.get(var)
        if idx is not None:
            features_interv[idx] = val

    x_orig = torch.tensor(features, dtype=torch.float32, device=_device).unsqueeze(0)
    x_interv = torch.tensor(features_interv, dtype=torch.float32, device=_device).unsqueeze(0)

    from app.models.inovacao.neko_pignn import NeKoPIGNN, build_ceara_graph
    if "neko" not in _model_cache:
        m = NeKoPIGNN(node_features=6, latent_dim=32, gnn_hidden=64, num_nodes=20).to(_device).eval()
        _model_cache["neko"] = m
    model = _model_cache["neko"]

    edge_index, edge_attr = build_ceara_graph(num_nodes=20, knn=3)
    edge_index, edge_attr = edge_index.to(_device), edge_attr.to(_device)

    with torch.no_grad():
        batch = torch.zeros(1, 20, 6, device=_device)
        batch[0, 0] = x_orig[0]
        out_orig = model(batch, edge_index, edge_attr)
        batch_interv = torch.zeros(1, 20, 6, device=_device)
        batch_interv[0, 0] = x_interv[0]
        out_interv = model(batch_interv, edge_index, edge_attr)

    risco_orig = float(torch.sigmoid(out_orig["z_t"].mean()).item())
    risco_interv = float(torch.sigmoid(out_interv["z_t"].mean()).item())
    delta = risco_interv - risco_orig

    return json.dumps({
        "municipio": municipio,
        "risco_atual": round(risco_orig, 3),
        "risco_intervencao": round(risco_interv, 3),
        "diferenca": round(delta, 3),
        "intervencao_aplicada": intervencao,
        "interpretacao": (
            f"Risco variou de {risco_orig:.1%} para {risco_interv:.1%} "
            f"({'+' if delta > 0 else ''}{delta:+.1%}). "
            f"{'A intervenção REDUZIU o risco.' if delta < 0 else 'Aumentou.' if delta > 0 else 'Sem alteração significativa.'}"
        ),
    }, ensure_ascii=False)


@tool
def analisar_features_shap(municipio_json: str) -> str:
    """Analisa importância de features (gradiente-based) para o risco.
    municipio_json: {"nome":"Beberibe", "features":[temp,frp,vento,umidade,ndvi,declividade]}
    Retorna quais features mais contribuem para o risco.
    """
    data = json.loads(municipio_json)
    features = np.array(data["features"], dtype=np.float32)
    var_names = ["temperatura", "frp", "vento", "umidade", "ndvi", "declividade"]

    x = torch.tensor(features, dtype=torch.float32, device=_device, requires_grad=True)

    from app.models.inovacao.koopman_operator import NeuralKoopmanOperator
    if "koopman" not in _model_cache:
        m = NeuralKoopmanOperator(input_dim=6, latent_dim=32, koopman_rank=16).to(_device).eval()
        _model_cache["koopman"] = m
    model = _model_cache["koopman"]

    z = model.encode(x.unsqueeze(0))
    risco = torch.sigmoid(z[0].mean())
    model.zero_grad()
    risco.backward()
    grad = x.grad.detach().cpu().numpy()
    importancia = np.abs(grad) / (np.sum(np.abs(grad)) + 1e-10)

    ranking = sorted(zip(var_names, importancia.tolist(), features.tolist()),
                     key=lambda t: t[1], reverse=True)

    return json.dumps({
        "municipio": data["nome"],
        "feature_importance": [
            {"variavel": v, "importancia": round(i, 3), "valor": round(vl, 2)}
            for v, i, vl in ranking
        ],
        "fator_mais_importante": ranking[0][0],
        "interpretacao": (
            f"Fator MAIS importante: '{ranking[0][0]}' ({ranking[0][1]:.1%}). "
            f"Segundo: '{ranking[1][0]}' ({ranking[1][1]:.1%}). "
        ),
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Lista de tools
# ---------------------------------------------------------------------------

_TOOLS = [
    buscar_clima_foco,
    analisar_intensidade_foco,
    analisar_risco_koopman,
    simulacao_causal,
    analisar_features_shap,
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Você é o Agente Explicador NeKo-PIGNN — especialista em explicar previsões
de queimadas feitas pelo modelo Neural Koopman + Physics-Informed GNN no Ceará, Brasil.

SEMPRE use as ferramentas antes de responder. NÃO invente dados.

Fluxo recomendado:
- Risco em região → analisar_risco_koopman
- "E se..." → simulacao_causal
- "Por que" / fatores → analisar_features_shap
- Clima → buscar_clima_foco
- Intensidade → analisar_intensidade_foco

Explique em português claro. Máximo 6 frases.
"""

# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_agent():
    """Constrói o agente ReAct usando create_agent() (LangChain 1.3+)."""
    llm = create_chat_llm(temperature=0.2, max_tokens=1024)
    return create_agent(
        model=llm,
        tools=_TOOLS,
        system_prompt=_SYSTEM_PROMPT,
        name="neko_explicador",
    )


# ---------------------------------------------------------------------------
# API de alto nível
# ---------------------------------------------------------------------------


async def explicar_risco(municipio: str, features: list[float]) -> dict:
    """Explica o risco de queimada em um município usando o agente."""
    agent = build_agent()
    features_json = json.dumps([features])
    municipios_json = json.dumps([municipio])

    prompt = (
        f"Analise o risco de queimada em {municipio}, Ceará.\n"
        f"Features: temp={features[0]:.1f}°C, FRP={features[1]:.1f}MW, "
        f"vento={features[2]:.1f}m/s, umidade={features[3]:.1f}%, "
        f"NDVI={features[4]:.3f}, declividade={features[5]:.1f}°.\n\n"
        f"Use analisar_risco_koopman com municipios_json='{municipios_json}' "
        f"e features_json='{features_json}'.\n"
        f"Depois use analisar_features_shap.\n"
        f"Explique o risco, os fatores mais importantes e uma recomendação."
    )
    try:
        resposta = agent.invoke({"messages": [("human", prompt)]})
        texto = resposta.get("messages", [{}])[-1].get("content", "")
    except Exception as e:
        logger.warning(f"Agente falhou: {e}")
        texto = f"Agente indisponível: {e}"

    return {
        "municipio": municipio,
        "explicacao": texto or "Não foi possível gerar explicação.",
        "modelo": "NeKo-PIGNN + DeepSeek ReAct",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def simular_cenario(municipio: str, features: list[float],
                          intervencao: dict[str, float]) -> dict:
    """Simula intervenção causal usando o agente."""
    agent = build_agent()
    prompt = (
        f"Simule o que aconteceria em {municipio} com intervenção {intervencao}.\n"
        f"Features: {features}\n"
        f"Use simulacao_causal.\nExplique o resultado."
    )
    try:
        resposta = agent.invoke({"messages": [("human", prompt)]})
        texto = resposta.get("messages", [{}])[-1].get("content", "")
    except Exception as e:
        texto = f"Simulação indisponível: {e}"
    return {"municipio": municipio, "intervencao": intervencao,
            "explicacao": texto, "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# CLI de teste
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    async def test():
        feats = [32.5, 15.3, 6.2, 35.0, 0.45, 5.0]
        r = await explicar_risco("Beberibe", feats)
        print("=== RISCO ===")
        print(r["explicacao"][:500])
        s = await simular_cenario("Beberibe", feats, {"umidade": 0.6, "vento": 2.0})
        print("\n=== SIMULAÇÃO ===")
        print(s["explicacao"][:500])
    asyncio.run(test())
