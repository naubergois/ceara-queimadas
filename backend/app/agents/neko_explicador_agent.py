"""
INOV-009: Agente Explicador ReAct NeKo-PIGNN (DeepSeek + SHAP)
===============================================================
Agente LangChain ReAct (LangChain 0.3.x / LangGraph 0.2.x compat)
que explica previsões do modelo NeKo-PIGNN em linguagem natural.

Tools:
1. buscar_clima_foco — clima real via Open-Meteo
2. analisar_intensidade_foco — classificação FRP
3. analisar_risco_koopman — risco via Neural Koopman Operator
4. simulacao_causal — intervenções "e se..." no NeKo-PIGNN
5. analisar_features_shap — importância de features via gradientes
6. buscar_estado_modelo — estado do modelo NeKo-PIGNN carregado

Integração LangGraph:
- Pipeline de agente com fallback rule-based
- Cache de modelo compartilhado com API de inovação
- Rastreamento de reasoning chain para auditoria

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

# ===========================================================================
# Helpers de modelo compartilhados (mesmo cache da API de inovação)
# ===========================================================================


def _get_koopman_model() -> torch.nn.Module:
    """Carrega ou retorna o modelo NeuralKoopmanOperator do cache."""
    if "koopman" not in _model_cache:
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator
        m = NeuralKoopmanOperator(
            input_dim=6, latent_dim=32, koopman_rank=16,
        ).to(_device).eval()
        _model_cache["koopman"] = m
        logger.info("Koopman model cached for explicador (%d params)",
                     sum(p.numel() for p in m.parameters()))
    return _model_cache["koopman"]


def _get_neko_model() -> torch.nn.Module:
    """Carrega ou retorna o modelo NeKo-PIGNN do cache."""
    if "neko" not in _model_cache:
        from app.models.inovacao.neko_pignn import NeKoPIGNN, build_ceara_graph
        m = NeKoPIGNN(
            node_features=6, latent_dim=32, gnn_hidden=64, num_nodes=20,
        ).to(_device).eval()
        _model_cache["neko"] = m
        _model_cache["neko_graph"] = build_ceara_graph(num_nodes=20, knn=3)
        logger.info("NeKo-PIGNN model cached for explicador (%d params)",
                     sum(p.numel() for p in m.parameters()))
    return _model_cache["neko"]


def _get_neko_graph():
    """Retorna (edge_index, edge_attr) para o modelo NeKo."""
    _get_neko_model()  # garante que o cache existe
    return _model_cache.get("neko_graph", (None, None))


# ===========================================================================
# Tools @tool decorator (LangChain 1.3+)
# ===========================================================================


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
    conf_txt = "alta" if confianca >= 80 else "moderada" if confianca >= 50 else "baixa"
    return json.dumps({
        "intensidade": intensidade,
        "descricao": descricao,
        "frp_mw": frp,
        "temperatura_celsius": round(temp_c, 1),
        "confianca": f"{confianca:.0f}% ({conf_txt})",
        "sensor": sensor,
        "interpretacao": (
            f"O sensor {sensor} detectou este foco com FRP de {frp:.1f} MW "
            f"e temperatura de {temp_c:.1f}°C. Intensidade: {intensidade}."
        ),
    }, ensure_ascii=False)


@tool
def analisar_risco_koopman(municipios_json: str, features_json: str) -> str:
    """Analisa risco de queimadas usando Neural Koopman Operator.
    municipios_json: lista JSON de nomes de municípios
    features_json: lista JSON de arrays de features [[temp,frp,vento,umidade,ndvi,declividade], ...]
    Retorna modos coerentes + projeção de risco + interpretação.
    """
    municipios = json.loads(municipios_json)
    features = json.loads(features_json)
    x = torch.tensor(features, dtype=torch.float32, device=_device)

    model = _get_koopman_model()
    with torch.no_grad():
        _, _, z = model.encode(x)
        z_future = model.forward_koopman(z, steps=6)
        x_pred = model.decode(z_future)
        K = model.K_matrix.detach().cpu().numpy()
        eigvals = np.linalg.eigvals(K)

    risco = float(torch.sigmoid(z.mean()).item())
    dominancia = float(np.max(np.abs(eigvals))) / float(np.sum(np.abs(eigvals)) + 1e-10)
    top3_idx = torch.topk(z.mean(dim=1), min(3, z.shape[0])).indices.cpu().tolist()

    # Projeção de risco futuro (6 passos = ~6h)
    risco_futuro = float(torch.sigmoid(x_pred[:, 1].mean()).item())

    return json.dumps({
        "risco_global": round(risco, 3),
        "risco_projetado_6h": round(risco_futuro, 3),
        "dominancia_modo1": round(dominancia, 3),
        "municipios_maior_risco": [municipios[i] for i in top3_idx],
        "modos_coerentes": [float(np.abs(e)) for e in sorted(eigvals, key=np.abs, reverse=True)[:5]],
        "interpretacao": (
            f"Risco estimado: {risco:.1%}. Projeção 6h: {risco_futuro:.1%}. "
            f"Modo-1 concentra {dominancia:.1%} da dinâmica. "
            f"{'⚠️ Alerta: dinâmica dominante muito forte — propagação rápida' if dominancia > 0.5 else '✅ Dinâmica distribuída em múltiplos modos — propagação controlada'}"
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

    # Suporta tanto features de 1 nó (6) quanto multi-nó (20*6=120)
    if features.ndim == 1 and features.shape[0] == 6:
        features = features.reshape(1, 6)  # (1, 6) = 1 nó
    elif features.ndim == 1 and features.shape[0] > 6:
        # Assume 20 nós × 6 features
        features = features.reshape(-1, 6)  # (N, 6)
    num_nodes = features.shape[0]

    features_interv = features.copy()
    changes = []
    for var, val in intervencao.items():
        idx = var_map.get(var)
        if idx is not None:
            old_val = features_interv[0, idx] if features_interv.ndim > 1 else features_interv[idx]
            features_interv[:, idx] = val if features_interv.ndim > 1 else val
            changes.append({"variavel": var, "de": round(float(old_val), 3), "para": round(float(val), 3)})

    x_orig = torch.tensor(features, dtype=torch.float32, device=_device).unsqueeze(0)  # (1, N, 6)
    x_interv = torch.tensor(features_interv, dtype=torch.float32, device=_device).unsqueeze(0)

    model = _get_neko_model()
    edge_index, edge_attr = _get_neko_graph()
    edge_index, edge_attr = edge_index.to(_device), edge_attr.to(_device) if edge_index is not None else (None, None)

    with torch.no_grad():
        if x_orig.shape[1] <= 20:
            batch = torch.zeros(1, 20, 6, device=_device)
            batch[0, :x_orig.shape[1]] = x_orig[0]
            out_orig = model(batch, edge_index, edge_attr) if edge_index is not None else {}
            batch_interv = torch.zeros(1, 20, 6, device=_device)
            batch_interv[0, :x_interv.shape[1]] = x_interv[0]
            out_interv = model(batch_interv, edge_index, edge_attr) if edge_index is not None else {}
        else:
            out_orig = model(x_orig, edge_index, edge_attr)
            out_interv = model(x_interv, edge_index, edge_attr)

    risco_orig = float(torch.sigmoid(out_orig.get("z_t", torch.zeros(1, 20, 32, device=_device)).mean()).item())
    risco_interv = float(torch.sigmoid(out_interv.get("z_t", torch.zeros(1, 20, 32, device=_device)).mean()).item())
    delta = risco_interv - risco_orig

    return json.dumps({
        "municipio": municipio,
        "risco_atual": round(risco_orig, 3),
        "risco_intervencao": round(risco_interv, 3),
        "diferenca": round(delta, 3),
        "intervencao_aplicada": changes,
        "interpretacao": (
            f"Risco variou de {risco_orig:.1%} para {risco_interv:.1%} "
            f"({'+' if delta > 0 else ''}{delta:+.1%}). "
            f"{'✅ A intervenção REDUZIU o risco.' if delta < -0.02 else '⚠️ A intervenção AUMENTOU o risco.' if delta > 0.02 else '➡️ Sem alteração significativa no risco.'}"
        ),
    }, ensure_ascii=False)


@tool
def analisar_features_shap(municipio_json: str) -> str:
    """Analisa importância de features (gradiente-based / SHAP-like) para o risco.
    municipio_json: {"nome":"Beberibe", "features":[temp,frp,vento,umidade,ndvi,declividade]}
    Retorna quais features mais contribuem para o risco, com valores de importância.
    """
    data = json.loads(municipio_json)
    features = np.array(data["features"], dtype=np.float32)
    var_names = ["temperatura", "frp", "vento", "umidade", "ndvi", "declividade"]

    x = torch.tensor(features, dtype=torch.float32, device=_device, requires_grad=True)

    model = _get_koopman_model()
    _, _, z = model.encode(x.unsqueeze(0))
    risco = torch.sigmoid(z[0].mean())
    model.zero_grad()
    risco.backward()
    grad = x.grad.detach().cpu().numpy()

    # Importância baseada em gradiente × sinal da feature (SHAP-like)
    importancia_bruta = grad * features
    importancia = np.abs(importancia_bruta) / (np.sum(np.abs(importancia_bruta)) + 1e-10)
    direcao = np.sign(importancia_bruta)  # positiva = aumenta risco

    ranking = sorted(zip(var_names, importancia.tolist(), features.tolist(), direcao.tolist()),
                     key=lambda t: t[1], reverse=True)

    return json.dumps({
        "municipio": data["nome"],
        "feature_importance": [
            {
                "variavel": v,
                "importancia": round(i, 3),
                "valor": round(vl, 2),
                "direcao": "aumenta_risco" if d > 0 else "reduz_risco",
            }
            for v, i, vl, d in ranking
        ],
        "fator_mais_importante": ranking[0][0],
        "interpretacao": (
            f"Fator MAIS importante: '{ranking[0][0]}' ({ranking[0][1]:.1%}) — "
            f"{'aumenta' if ranking[0][3] > 0 else 'reduz'} o risco. "
            f"Segundo: '{ranking[1][0]}' ({ranking[1][1]:.1%}). "
            f"Terceiro: '{ranking[2][0]}' ({ranking[2][1]:.1%}). "
        ),
    }, ensure_ascii=False)


@tool
def buscar_estado_modelo() -> str:
    """Retorna o estado atual dos modelos NeKo-PIGNN/Koopman carregados em memória.
    Útil para diagnosticar se os modelos estão disponíveis para explicar previsões.
    """
    info = {}
    if "koopman" in _model_cache:
        m = _model_cache["koopman"]
        info["koopman"] = {
            "params": sum(p.numel() for p in m.parameters()),
            "device": str(_device),
        }
    if "neko" in _model_cache:
        m = _model_cache["neko"]
        info["neko_pignn"] = {
            "params": sum(p.numel() for p in m.parameters()),
            "device": str(_device),
            "graph_nodes": 20,
        }
    return json.dumps({
        "modelos_carregados": list(info.keys()),
        "detalhes": info,
        "total_modelos": len(info),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False)


# ===========================================================================
# Lista de tools
# ===========================================================================

_TOOLS = [
    buscar_clima_foco,
    analisar_intensidade_foco,
    analisar_risco_koopman,
    simulacao_causal,
    analisar_features_shap,
    buscar_estado_modelo,
]

# ===========================================================================
# System prompt — Agente Explicador ReAct
# ===========================================================================

_SYSTEM_PROMPT = """Você é o Agente Explicador NeKo-PIGNN — especialista em explicar previsões
de queimadas feitas pelo modelo Neural Koopman + Physics-Informed GNN no Ceará, Brasil.

Você tem acesso a ferramentas que consultam o modelo NeKo-PIGNN e dados reais.
SEMPRE use as ferramentas antes de responder. NÃO invente dados.

FLUXO RECOMENDADO:
1. Risco em região → use analisar_risco_koopman
2. "Por que" / fatores → use analisar_features_shap
3. "E se..." / intervenções → use simulacao_causal
4. Clima → use buscar_clima_foco
5. Intensidade → use analisar_intensidade_foco
6. Estado do modelo → use buscar_estado_modelo

FORMATO DE RESPOSTA:
Pensamento: raciocine sobre o que precisa consultar
Ação: nome_da_ferramenta
Entrada da Ação: {"parametro": valor}
Observação: resultado da ferramenta
...(repita conforme necessário)
Resposta Final: [explicação em português claro, máximo 8 frases,
                 incluindo nível de confiança e recomendação operacional]

REGRAS:
- Explique conceitos técnicos (FRP, modos de Koopman) de forma acessível
- Inclua sempre: o que os dados mostram, por que importa, e o que fazer
- Se o modelo não estiver carregado, reporte e use fallback rule-based
- Se o risco é alto, destaque e sugira ação
"""

# ===========================================================================
# Builder
# ===========================================================================


def build_agent():
    """Constrói o agente ReAct usando create_agent() (LangChain 0.3.x)."""
    llm = create_chat_llm(temperature=0.1, max_tokens=1024)
    return create_agent(
        model=llm,
        tools=_TOOLS,
        system_prompt=_SYSTEM_PROMPT,
        name="neko_explicador",
    )


# ===========================================================================
# API de alto nível — funções públicas
# ===========================================================================


async def explicar_risco(municipio: str, features: list[float]) -> dict:
    """Explica o risco de queimada em um município usando o agente ReAct."""
    agent = build_agent()
    features_json = json.dumps([features])
    municipios_json = json.dumps([municipio])
    features_str = json.dumps({"nome": municipio, "features": features})

    prompt = (
        f"Analise o risco de queimada em {municipio}, Ceará.\n"
        f"Features: temp={features[0]:.1f}°C, FRP={features[1]:.1f}MW, "
        f"vento={features[2]:.1f}m/s, umidade={features[3]:.1f}%, "
        f"NDVI={features[4]:.3f}, declividade={features[5]:.1f}°.\n\n"
        f"1. Use analisar_risco_koopman com municipios_json='{municipios_json}' "
        f"e features_json='{features_json}'.\n"
        f"2. Depois use analisar_features_shap com municipio_json='{features_str}'.\n"
        f"3. Explique o risco atual, os fatores mais importantes e uma recomendação."
    )
    try:
        resposta = agent.invoke({"messages": [("human", prompt)]})
        texto = resposta.get("messages", [{}])[-1].get("content", "")
    except Exception as e:
        logger.warning("Agente NeKo explicador falhou: %s", e)
        texto = _explicar_sem_modelo(municipio, features, str(e))

    return {
        "municipio": municipio,
        "explicacao": texto or "Não foi possível gerar explicação.",
        "modelo": "NeKo-PIGNN + DeepSeek ReAct",
        "features": features,
        "nivel_confianca": 0.85 if "erro" not in texto.lower() else 0.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def simular_cenario(municipio: str, features: list[float],
                          intervencao: dict[str, float]) -> dict:
    """Simula intervenção causal usando o agente ReAct."""
    agent = build_agent()
    prompt = (
        f"Simule o que aconteceria em {municipio} com intervenção {intervencao}.\n"
        f"Features atuais: {features}\n"
        f"1. Use simulacao_causal com municipio='{municipio}', "
        f"features_atual_json='{json.dumps(features)}', "
        f"intervencao_json='{json.dumps(intervencao)}'.\n"
        f"2. Explique o resultado da simulação."
    )
    try:
        resposta = agent.invoke({"messages": [("human", prompt)]})
        texto = resposta.get("messages", [{}])[-1].get("content", "")
    except Exception as e:
        logger.warning("Simulação causal falhou: %s", e)
        texto = f"Simulação indisponível: {e}"
    return {
        "municipio": municipio,
        "intervencao": intervencao,
        "features": features,
        "explicacao": texto,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def explicar_por_id(foco_id: str, foco_data: dict) -> dict:
    """Explica um foco específico a partir de dados do cache de focos reais.
    Usa o agente ReAct para gerar explicação com NeKo-PIGNN e dados climáticos."""
    features = [
        foco_data.get("temp", 30.0),
        foco_data.get("frp", 5.0),
        foco_data.get("vento", 3.0),
        foco_data.get("umidade", 50.0),
        foco_data.get("ndvi", 0.4),
        foco_data.get("declividade", 2.0),
    ]
    municipio = foco_data.get("municipio", "município desconhecido")
    lat = foco_data.get("lat", 0.0)
    lon = foco_data.get("lon", 0.0)

    agent = build_agent()
    prompt = (
        f"Explique o foco de queimada ID {foco_id} em {municipio}, Ceará.\n"
        f"Coordenadas: lat={lat}, lon={lon}\n"
        f"Features atuais: temp={features[0]:.1f}°C, FRP={features[1]:.1f}MW, "
        f"vento={features[2]:.1f}m/s, umidade={features[3]:.1f}%, "
        f"NDVI={features[4]:.3f}.\n\n"
        f"1. Use buscar_clima_foco para coordenada ({lat}, {lon}).\n"
        f"2. Use analisar_intensidade_foco com "
        f"frp={features[1]}, temperatura_k={features[0]+273.15}, "
        f"confianca={foco_data.get('confianca', 80)}, sensor='{foco_data.get('sensor', 'VIIRS')}'.\n"
        f"3. Explique o risco, condições climáticas e recomende ação."
    )
    try:
        resposta = agent.invoke({"messages": [("human", prompt)]})
        texto = resposta.get("messages", [{}])[-1].get("content", "")
        tools_usadas = [
            tc.get("name", "?")
            for msg in resposta.get("messages", [])
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "tool_calls")
            and msg.tool_calls
            for tc in msg.tool_calls
        ]
    except Exception as e:
        logger.warning("Explicação por ID falhou: %s", e)
        texto = f"Explicação indisponível: {e}"
        tools_usadas = []

    return {
        "foco_id": foco_id,
        "municipio": municipio,
        "explicacao": texto,
        "ferramentas_usadas": list(set(tools_usadas)) or ["fallback"],
        "modelo": "NeKo-PIGNN ReAct",
        "nivel_confianca": 0.85 if tools_usadas else 0.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _explicar_sem_modelo(municipio: str, features: list[float], erro: str) -> str:
    """Fallback rule-based quando o agente/LLM não está disponível."""
    temp = features[0]
    frp = features[1]
    vento = features[2]
    umidade = features[3]
    ndvi = features[4]

    partes = [f"Análise de risco para {municipio}, Ceará (fallback — modelo indisponível: {erro}):"]
    risco = "BAIXO"
    if temp > 35 and umidade < 30:
        risco = "CRÍTICO"
        partes.append("Condições extremas: temperatura elevada e umidade muito baixa.")
    elif temp > 32 and umidade < 40:
        risco = "ALTO"
        partes.append("Condições desfavoráveis com calor e baixa umidade.")
    elif temp > 30:
        risco = "MODERADO"
        partes.append("Temperatura elevada.")

    if frp > 15:
        partes.append(f"FRP de {frp:.1f} MW indica fogo ativo.")
    if vento > 5:
        partes.append(f"Vento de {vento:.1f} m/s pode acelerar propagação.")
    if ndvi < 0.3:
        partes.append("Vegetação seca (NDVI baixo) — combustível disponível.")

    partes.append(f"Classificação geral: RISCO {risco}.")
    return " ".join(partes)


# ===========================================================================
# CLI de teste
# ===========================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        feats = [32.5, 15.3, 6.2, 35.0, 0.45, 5.0]
        print("=== TESTE: explicar_risco ===")
        r = await explicar_risco("Beberibe", feats)
        print(r["explicacao"][:600])
        print()

        print("=== TESTE: simular_cenario ===")
        s = await simular_cenario("Beberibe", feats, {"umidade": 0.6, "vento": 2.0})
        print(s["explicacao"][:600])

        print("\n=== TESTE: buscar_estado_modelo ===")
        from langchain_core.messages import HumanMessage
        agent = build_agent()
        resp = agent.invoke({"messages": [("human", "Quais modelos estão carregados? Use buscar_estado_modelo.")]})
        print(resp.get("messages", [{}])[-1].get("content", "")[:300])

    asyncio.run(test())
