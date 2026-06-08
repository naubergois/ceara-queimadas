"""
INOV-004: Endpoint API para Modelos de Inovação
================================================
Endpoints FastAPI para servir os modelos NeKo-PIGNN, Koopman Operator,
PI-GNN, análise causal e comparação com baselines.

Rotas:
  - POST /api/v1/prever-koopman
  - POST /api/v1/prever-pignn
  - POST /api/v1/prever-neko-pignn
  - GET  /api/v1/modos-coerentes
  - POST /api/v1/analise-causal
  - GET  /api/v1/comparar-baseline
  - GET  /api/v1/status-modelos
"""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import torch
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Inovação — Modelos"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PrevisaoRequest(BaseModel):
    municipios: list[str] = Field(
        ..., description="Lista de municípios do Ceará",
        max_length=184,
    )
    features: list[list[float]] = Field(
        ...,
        description="Features por município: [temp, frp, vento, umidade, ndvi, declividade, ...]",
    )
    horas_previsao: int = Field(default=6, ge=1, le=72, description="Horas à frente")


class PrevisaoResponse(BaseModel):
    modelo: str
    previsoes: list[dict]
    municipios: list[str]
    timestamp: str
    metadados: dict


class ModosCoerentesResponse(BaseModel):
    modos: list[dict]
    autovalores: list[float]
    explicacao: str


class AnaliseCausalRequest(BaseModel):
    municipio: str
    variaveis: dict = Field(
        ...,
        description="Intervenção causal: {variavel: novo_valor}",
        examples=[{"vento": 0.5, "umidade": 0.3, "vegetacao_seca": 0.8}],
    )
    horas_previsao: int = Field(default=24, ge=1, le=168)


class ComparacaoBaselineResponse(BaseModel):
    baseline: str
    rmse: float
    mae: float
    r2: float
    f1_score: float
    tempo_inferencia_ms: float


# ---------------------------------------------------------------------------
# Cache dos modelos (carregados sob demanda)
# ---------------------------------------------------------------------------

_model_cache: dict[str, torch.nn.Module] = {}
_model_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model(model_name: str) -> torch.nn.Module:
    """Carrega modelo do cache ou do disco."""
    if model_name in _model_cache:
        return _model_cache[model_name]

    model_paths = {
        "koopman": "backend/app/models/inovacao/koopman_operator.py",
        "pignn": "backend/app/models/inovacao/pignn.py",
        "neko_pignn": "backend/app/models/inovacao/neko_pignn.py",
    }

    if model_name not in model_paths:
        raise HTTPException(status_code=404, detail=f"Modelo '{model_name}' não encontrado")

    logger.info(f"Carregando modelo {model_name}...")

    if model_name == "koopman":
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator
        model = NeuralKoopmanOperator(
            input_dim=6, latent_dim=32, koopman_rank=16
        )
    elif model_name == "pignn":
        from app.models.inovacao.pignn import PhysicsInformedGNN
        model = PhysicsInformedGNN(
            node_features=8, hidden_dim=64, num_layers=4, output_dim=3
        )
    elif model_name == "neko_pignn":
        from app.models.inovacao.neko_pignn import NeKoPIGNN
        model = NeKoPIGNN(
            node_features=6, latent_dim=32, gnn_hidden=64, num_nodes=184
        )

    model = model.to(_model_device)
    model.eval()
    _model_cache[model_name] = model
    logger.info(f"Modelo {model_name} carregado ({sum(p.numel() for p in model.parameters()):,} params)")
    return model


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.post("/prever-koopman", response_model=PrevisaoResponse)
async def prever_koopman(req: PrevisaoRequest):
    """
    Previsão usando Neural Koopman Operator.
    Projeta a dinâmica de cada município independentemente no espaço de Koopman.
    """
    try:
        model = _load_model("koopman")

        # Converte para tensor
        x_t = torch.tensor(req.features, dtype=torch.float32, device=_model_device)

        # Codifica e propaga
        with torch.no_grad():
            _, _, z_t = model.encode(x_t)
            z_future = model.forward_koopman(z_t, steps=req.horas_previsao)
            x_pred = model.decode(z_future)

        # Formata resposta
        previsoes = []
        for i, municipio in enumerate(req.municipios):
            previsoes.append({
                "municipio": municipio,
                "features_previstas": x_pred[i].cpu().tolist(),
                "confianca": float(torch.sigmoid(z_t[i].mean()).item()),
            })

        return PrevisaoResponse(
            modelo="NeuralKoopmanOperator",
            previsoes=previsoes,
            municipios=req.municipios,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadados={
                "passos_previsao": req.horas_previsao,
                "dimensao_latente": model.latent_dim,
                "parametros": sum(p.numel() for p in model.parameters()),
            },
        )
    except Exception as e:
        logger.error(f"Erro ao executar Koopman: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prever-pignn", response_model=PrevisaoResponse)
async def prever_pignn(req: PrevisaoRequest):
    """
    Previsão usando Physics-Informed GNN.
    Propaga fogo entre municípios vizinhos com regularização física de Rothermel.
    """
    try:
        model = _load_model("pignn")

        # Constrói grafo KNN dos municípios
        from app.models.inovacao.neko_pignn import build_ceara_graph
        edge_index, edge_attr = build_ceara_graph(num_nodes=len(req.municipios), knn=5)
        edge_index = edge_index.to(_model_device)
        edge_attr = edge_attr.to(_model_device)

        # Tensor de entrada
        x = torch.tensor(req.features, dtype=torch.float32, device=_model_device)
        x = x.unsqueeze(0)  # adiciona batch

        with torch.no_grad():
            pred = model(x, edge_index, edge_attr)

        previsoes = []
        for i, municipio in enumerate(req.municipios):
            previsoes.append({
                "municipio": municipio,
                "features_previstas": pred[0, i].cpu().tolist(),
            })

        return PrevisaoResponse(
            modelo="PhysicsInformedGNN",
            previsoes=previsoes,
            municipios=req.municipios,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadados={
                "num_nos": len(req.municipios),
                "num_arestas": edge_index.shape[1],
                "parametros": sum(p.numel() for p in model.parameters()),
            },
        )
    except Exception as e:
        logger.error(f"Erro ao executar PI-GNN: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prever-neko-pignn", response_model=PrevisaoResponse)
async def prever_neko_pignn(req: PrevisaoRequest):
    """
    Previsão usando o modelo híbrido NeKo-PIGNN completo.
    Combina Koopman (linearização temporal) + GNN (propagação espacial) + Rothermel Loss.
    """
    try:
        model = _load_model("neko_pignn")

        # Grafo
        from app.models.inovacao.neko_pignn import build_ceara_graph
        edge_index, edge_attr = build_ceara_graph(num_nodes=len(req.municipios), knn=5)
        edge_index = edge_index.to(_model_device)
        edge_attr = edge_attr.to(_model_device)

        x_t = torch.tensor(req.features, dtype=torch.float32, device=_model_device)
        x_t = x_t.unsqueeze(0)  # (1, num_nodes, features)

        with torch.no_grad():
            outputs = model(
                x_t,
                edge_index=edge_index,
                edge_attr=edge_attr,
            )
            x_pred = outputs["x_pred"]  # (1, num_nodes, features)
            z_coherent = outputs.get("z_t", None)

        previsoes = []
        for i, municipio in enumerate(req.municipios):
            previsoes.append({
                "municipio": municipio,
                "features_previstas": x_pred[0, i].cpu().tolist(),
                "estado_latente": z_coherent[0, i, :8].cpu().tolist() if z_coherent is not None else [],
            })

        return PrevisaoResponse(
            modelo="NeKo-PIGNN",
            previsoes=previsoes,
            municipios=req.municipios,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadados={
                "modelo_hibrido": True,
                "dimensao_latente": model.latent_dim,
                "regularizacao_fisica": "RothermelLoss",
                "parametros": sum(p.numel() for p in model.parameters()),
            },
        )
    except Exception as e:
        logger.error(f"Erro ao executar NeKo-PIGNN: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modos-coerentes", response_model=ModosCoerentesResponse)
async def modos_coerentes(
    municipios: str = Query(default="[]", description="Lista JSON de municípios"),
    features: str = Query(default="[]", description="Lista JSON de features"),
):
    """
    Retorna os modos coerentes de Koopman (autofunções).
    Os autovetores da matriz K revelam padrões de propagação:
    - Modo dominante: direção principal de propagação
    - Modos secundários: padrões sazonais/regionais
    """
    try:
        model = _load_model("koopman")

        # Matriz K
        K = model.K_matrix.detach().cpu().numpy()

        # Decomposição espectral
        eigenvalues, eigenvectors = np.linalg.eig(K)

        # Ordena por magnitude
        idx = np.argsort(np.abs(eigenvalues))[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        modos = []
        for i in range(min(5, len(eigenvalues))):
            modo = {
                "modo": i + 1,
                "autovalor": float(np.abs(eigenvalues[i])),
                "fase": float(np.angle(eigenvalues[i])),
                "dominancia": float(np.abs(eigenvalues[i]) / np.sum(np.abs(eigenvalues))),
                "autovetor": eigenvectors[:8, i].real.tolist(),
                "interpretacao": _interpretar_modo(i, eigenvalues[i]),
            }
            modos.append(modos)

        return ModosCoerentesResponse(
            modos=modos,
            autovalores=[float(np.abs(e)) for e in eigenvalues[:10]],
            explicacao=(
                "Os modos coerentes de Koopman revelam os padrões intrínsecos "
                "de propagação do fogo. O modo 1 (dominante) indica a direção "
                "principal de propagação. Modos com autovalor próximo de 1 "
                "representam dinâmicas quase-periódicas (ex: ciclo diário de "
                "queimadas). Modos com |λ| < 1 amortecidos (extinção)."
            ),
        )
    except Exception as e:
        logger.error(f"Erro modos coerentes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _interpretar_modo(modo_idx: int, autovalor: complex) -> str:
    """Interpreta cada modo de Koopman em linguagem natural."""
    mag = abs(autovalor)
    phase = np.angle(autovalor)

    if modo_idx == 0:
        return f"Modo dominante (|λ|={mag:.3f}) — direção principal de propagação do fogo no Ceará"
    elif mag > 0.9:
        return f"Modo quase-periódico (|λ|={mag:.3f}, φ={phase:.2f} rad) — ciclo sazonal de queimadas"
    elif mag > 0.7:
        return f"Modo intermediário (|λ|={mag:.3f}) — padrão regional de propagação"
    else:
        return f"Modo amortecido (|λ|={mag:.3f}) — dinâmica local de curta duração"


@router.post("/analise-causal", response_model=dict)
async def analise_causal(req: AnaliseCausalRequest):
    """
    Análise de intervenções causais (do-calculus).
    Responde: "O que aconteceria se a variável X mudasse para Y?"

    Usa o modelo NeKo-PIGNN para simular cenários contrafactuais.
    """
    try:
        # Carrega modelo
        model = _load_model("neko_pignn")

        # Cria cenário base e cenário intervencionado
        # (simplificado — em produção usar dados reais do município)
        num_features = 6
        base_state = torch.randn(1, 1, num_features, device=_model_device)

        # Aplica intervenção causal (substitui variáveis)
        intervened_state = base_state.clone()
        var_map = {
            "temperatura": 0, "frp": 1, "vento": 2,
            "umidade": 3, "ndvi": 4, "declividade": 5,
        }
        for var_name, value in req.variaveis.items():
            if var_name in var_map:
                intervened_state[0, 0, var_map[var_name]] = value

        # Simula cenário contrafactual
        from app.models.inovacao.neko_pignn import build_ceara_graph
        edge_index, edge_attr = build_ceara_graph(num_nodes=1, knn=2)
        edge_index = edge_index.to(_model_device)
        edge_attr = edge_attr.to(_model_device)

        with torch.no_grad():
            base_pred = model(base_state, edge_index=edge_index, edge_attr=edge_attr)
            interv_pred = model(intervened_state, edge_index=edge_index, edge_attr=edge_attr)

        # Diferença causal
        diff = (interv_pred["x_pred"] - base_pred["x_pred"]).cpu().squeeze().tolist()

        return {
            "municipio": req.municipio,
            "intervencao_aplicada": req.variaveis,
            "diferenca_causal": {
                "delta_temperatura": diff[0],
                "delta_frp": diff[1],
                "delta_risco": diff[2] if len(diff) > 2 else None,
            },
            "interpretacao": _interpretar_intervencao(req.variaveis, diff),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Erro análise causal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _interpretar_intervencao(variaveis: dict, diff: list) -> str:
    """Interpreta o resultado da intervenção causal."""
    partes = []
    if diff[1] > 0.1:
        partes.append(f"A intervenção {' + '.join(variaveis.keys())} AUMENTOU o FRP em {diff[1]:.2f} — maior risco de propagação")
    elif diff[1] < -0.1:
        partes.append(f"A intervenção REDUZIU o FRP em {abs(diff[1]):.2f} — menor risco")
    else:
        partes.append("Mudança marginal no FRP — impacto na propagação é pequeno")
    return ". ".join(partes)


@router.get("/comparar-baseline", response_model=list[ComparacaoBaselineResponse])
async def comparar_baseline(
    modelo_principal: str = Query(default="neko_pignn", description="Modelo principal a comparar"),
    dataset: str = Query(default="real", description="Dataset: 'real' (FIRMS+INPE) ou 'sintetico'"),
):
    """
    Compara o modelo NeKo-PIGNN com baselines.
    Resultados de validação experimental real (TASK-083 v2/v3).
    """
    if dataset == "real":
        # Resultados reais do experimento v3 (dados NASA FIRMS + INPE + Open-Meteo)
        baselines = [
            ComparacaoBaselineResponse(baseline="MLP", rmse=0.1377, mae=0.0993, r2=0.7986, f1_score=0.9407, tempo_inferencia_ms=0.01),
            ComparacaoBaselineResponse(baseline="LSTM", rmse=0.1631, mae=0.1268, r2=0.7182, f1_score=0.9431, tempo_inferencia_ms=0.4),
            ComparacaoBaselineResponse(baseline="XGBoost", rmse=0.1485, mae=0.1115, r2=0.7660, f1_score=0.9311, tempo_inferencia_ms=5.6),
            ComparacaoBaselineResponse(baseline="Koopman-Det (ours)", rmse=0.1569, mae=0.1148, r2=0.7388, f1_score=0.9243, tempo_inferencia_ms=0.1),
            ComparacaoBaselineResponse(baseline="NeKo-PIGNN v2 (ours)", rmse=0.1516, mae=0.1099, r2=0.7561, f1_score=0.9257, tempo_inferencia_ms=0.3),
        ]
    else:
        # Resultados do experimento v2 (dados sintéticos, 500 timesteps, 30 nós)
        baselines = [
            ComparacaoBaselineResponse(baseline="MLP", rmse=0.0687, mae=0.0237, r2=0.9677, f1_score=0.9750, tempo_inferencia_ms=0.01),
            ComparacaoBaselineResponse(baseline="LSTM", rmse=0.0841, mae=0.0446, r2=0.9512, f1_score=0.9448, tempo_inferencia_ms=0.8),
            ComparacaoBaselineResponse(baseline="XGBoost", rmse=0.0871, mae=0.0387, r2=0.9480, f1_score=0.9311, tempo_inferencia_ms=4.4),
            ComparacaoBaselineResponse(baseline="Koopman-Det (ours)", rmse=0.0680, mae=0.0224, r2=0.9683, f1_score=0.9751, tempo_inferencia_ms=0.1),
            ComparacaoBaselineResponse(baseline="NeKo-PIGNN v2 (ours)", rmse=0.0640, mae=0.0241, r2=0.9719, f1_score=0.9751, tempo_inferencia_ms=0.4),
            ComparacaoBaselineResponse(baseline="NeKo-GNN (no physics)", rmse=0.0664, mae=0.0216, r2=0.9698, f1_score=0.9764, tempo_inferencia_ms=0.4),
        ]

    return baselines


@router.get("/status-modelos", response_model=dict)
async def status_modelos():
    """Status dos modelos de inovação carregados em memória."""
    return {
        "modelos_carregados": list(_model_cache.keys()),
        "dispositivo": str(_model_device),
        "total_modelos": len(_model_cache),
        "parametros_total": sum(
            sum(p.numel() for p in m.parameters())
            for m in _model_cache.values()
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Novos endpoints v2: Previsão operacional com Koopman Determinístico + GNN
# ---------------------------------------------------------------------------


@router.get("/prever-risco-municipios", response_model=dict)
async def prever_risco_municipios(
    horas_frente: int = Query(default=6, ge=1, le=72, description="Horas à frente para previsão"),
):
    """
    Previsão operacional de risco por município usando NeKo-PIGNN v2.

    Combina:
    - Koopman Determinístico (propagação temporal)
    - GNN com adjacência real (propagação espacial)
    - Score Rothermel (regularização física)

    Usa dados reais do cache (NASA FIRMS + Open-Meteo).
    """
    try:
        from app.services.predicao_v2 import get_operational_model, compute_risk_index, MUNICIPIOS_CE
        from app.api.focos_reais import _cache_focos, _cache_clima

        model, adj = get_operational_model()

        # Construir features atuais a partir do cache
        num_mun = len(MUNICIPIOS_CE)
        features = np.zeros((num_mun, 6))

        # Default features (normalizado 0-1)
        for i, (mun, (lat, lon)) in enumerate(MUNICIPIOS_CE.items()):
            # Buscar clima do município mais próximo no cache
            clima_mun = None
            if _cache_clima:
                for c in _cache_clima:
                    if mun.lower() in c.get("municipio", "").lower():
                        clima_mun = c
                        break

            if clima_mun:
                features[i, 0] = min(1.0, max(0.0, (clima_mun.get("temperatura", 30) - 20) / 20))
                features[i, 2] = min(1.0, max(0.0, clima_mun.get("vento_kmh", 5) / 30))
                features[i, 3] = min(1.0, max(0.0, clima_mun.get("umidade", 60) / 100))
                features[i, 4] = min(1.0, max(0.0, clima_mun.get("precipitacao", 0) / 50))
            else:
                features[i, 0] = 0.5  # temp default
                features[i, 3] = 0.5  # umidade default

            # Contar focos por município no cache
            focos_mun = 0
            if _cache_focos:
                for f in _cache_focos:
                    f_mun = f.get("municipio", "")
                    if f_mun and mun.lower() in f_mun.lower():
                        focos_mun += 1
            features[i, 1] = min(1.0, focos_mun / 10.0)  # FRP proxy
            features[i, 5] = 0.1  # declividade constante

        # Predizer
        x_t = torch.tensor(features, dtype=torch.float32).unsqueeze(0)  # (1, nodes, 6)
        steps = max(1, horas_frente // 6)

        with torch.no_grad():
            prediction = model(x_t, adj, steps=steps)

        riscos = compute_risk_index(prediction, features)

        return {
            "previsao_horas": horas_frente,
            "modelo": "NeKo-PIGNN v2 (Koopman-Det + GNN + Rothermel)",
            "spectral_radius": prediction["spectral_radius"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "municipios_risco": riscos,
            "resumo": {
                "total_municipios": num_mun,
                "critico": sum(1 for r in riscos if r["classificacao"] == "critico"),
                "alto": sum(1 for r in riscos if r["classificacao"] == "alto"),
                "medio": sum(1 for r in riscos if r["classificacao"] == "medio"),
                "baixo": sum(1 for r in riscos if r["classificacao"] == "baixo"),
            },
            "metodologia": {
                "linha_b": "PEAK + PERSIST + FUSÃO (score composto temporal)",
                "linha_e": "Consenso multi-vista (modelo + Rothermel + condições)",
                "modelo": "Koopman Determinístico + GNN + Rothermel Loss",
                "referencia": "docs/METODOLOGIA_NOVA_PROPOSTA.md",
            },
        }
    except Exception as e:
        logger.error(f"Erro previsão risco: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experimentos/resultados", response_model=dict)
async def resultados_experimentos():
    """
    Retorna os resultados dos experimentos de validação (TASK-083 v1, v2, v3).
    Dados de benchmark comparando NeKo-PIGNN com baselines.
    """
    import json as _json
    from pathlib import Path

    results_dir = Path(__file__).parent.parent.parent / "experiments" / "results"

    output = {"experimentos": []}

    # v2 — sintético
    v2_path = results_dir / "benchmark_results_v2.json"
    if v2_path.exists():
        with open(v2_path) as f:
            output["experimentos"].append(_json.load(f))

    # v3 — dados reais
    v3_path = results_dir / "benchmark_results_real.json"
    if v3_path.exists():
        with open(v3_path) as f:
            output["experimentos"].append(_json.load(f))

    output["total_experimentos"] = len(output["experimentos"])
    output["conclusao"] = (
        "NeKo-PIGNN v2 alcança melhor RMSE (0.064) e R² (0.972) em dados sintéticos, "
        "superando MLP, LSTM e XGBoost. Em dados reais (97 dias, 377 focos), é competitivo "
        "(3º em RMSE com margem mínima de 0.014 vs MLP) com Recall ≥ 96%."
    )

    return output
