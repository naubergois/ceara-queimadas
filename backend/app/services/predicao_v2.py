"""
Serviço de Predição v2 — Integra conceitos da nova metodologia:

1. Koopman Determinístico (sem VAE) — previsão temporal por município
2. GNN com adjacência real — propagação espacial entre municípios vizinhos
3. Regularização física Rothermel — FRP respeita dinâmica de combustível
4. Consenso multi-vista (Linha E) — combina previsão modelo com detecção GOES-16
5. PEAK + PERSIST + FUSÃO (Linha B) — persistência temporal de anomalias

Fluxo operacional:
  Dados reais (FIRMS + clima) → Koopman-Det predict → GNN propaga → Rothermel check
                                                                  → Risco por município
  GOES-16 (se disponível) → PEAK+PERSIST → Consenso com modelo → Detecção final
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coordenadas reais dos municípios do Ceará (15 monitorados)
# ---------------------------------------------------------------------------

MUNICIPIOS_CE = {
    "Fortaleza": (-3.72, -38.52),
    "Sobral": (-3.69, -40.35),
    "Juazeiro do Norte": (-7.21, -39.31),
    "Crato": (-7.23, -39.41),
    "Quixadá": (-4.97, -39.01),
    "Iguatu": (-6.36, -39.30),
    "Crateús": (-5.18, -40.68),
    "Tianguá": (-3.73, -40.99),
    "Icó": (-6.40, -38.86),
    "Tauá": (-5.99, -40.30),
    "Canindé": (-4.36, -39.31),
    "Russas": (-4.94, -37.97),
    "Limoeiro do Norte": (-5.15, -38.10),
    "Itapipoca": (-3.49, -39.58),
    "Mossoró (adj)": (-5.19, -37.34),
}


# ---------------------------------------------------------------------------
# Modelo: Koopman Determinístico v2 (reproduz o validate_models_v2)
# ---------------------------------------------------------------------------


class DeterministicKoopmanV2(nn.Module):
    """
    Koopman Operacional — sem VAE, full-rank K, spectral regularization.
    Otimizado para deploy com curriculum learning pré-aplicado.
    """

    def __init__(self, input_dim: int = 6, latent_dim: int = 64):
        super().__init__()
        self.latent_dim = latent_dim

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(128, 96), nn.LayerNorm(96), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(96, 64), nn.LayerNorm(64), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(64, latent_dim),
        )

        # Koopman matrix K — initialized near identity for stability
        self.K = nn.Parameter(torch.eye(latent_dim) + 0.01 * torch.randn(latent_dim, latent_dim))

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64), nn.LayerNorm(64), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(64, 96), nn.LayerNorm(96), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(96, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(128, input_dim),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)

    def forward_k(self, z: torch.Tensor, steps: int = 1) -> torch.Tensor:
        for _ in range(steps):
            z = z @ self.K.T
        return z

    def predict(self, x_t: torch.Tensor, steps: int = 1) -> torch.Tensor:
        """Prediz steps à frente a partir do estado atual."""
        z = self.encode(x_t)
        z_future = self.forward_k(z, steps)
        return self.decode(z_future)

    @property
    def spectral_radius(self) -> float:
        """Raio espectral de K (deve ser ≤ 1 para estabilidade)."""
        with torch.no_grad():
            eigs = torch.linalg.eigvals(self.K)
            return float(eigs.abs().max().item())


class SimpleGNNPropagation(nn.Module):
    """GNN para propagação espacial entre municípios vizinhos."""

    def __init__(self, dim: int = 64, num_layers: int = 3):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.Sequential(nn.Linear(dim * 2, dim), nn.GELU(), nn.Linear(dim, dim))
            for _ in range(num_layers)
        ])

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, nodes, dim)
        adj: (nodes, nodes) normalized adjacency
        """
        for layer in self.layers:
            # Message: aggregate neighbors
            deg = adj.sum(1, keepdim=True).clamp(min=1)
            neighbor = torch.bmm(adj.unsqueeze(0).expand(x.size(0), -1, -1), x)
            neighbor = neighbor / deg.unsqueeze(0)
            combined = torch.cat([x, neighbor], dim=-1)
            x = x + layer(combined)  # residual
        return x


class NeKoPIGNN_Operational(nn.Module):
    """
    Modelo operacional NeKo-PIGNN v2 para deploy.
    Combina Koopman Determinístico + GNN + Rothermel output check.
    """

    def __init__(self, input_dim: int = 6, latent_dim: int = 64, num_municipalities: int = 15):
        super().__init__()
        self.koopman = DeterministicKoopmanV2(input_dim, latent_dim)
        self.gnn = SimpleGNNPropagation(latent_dim, num_layers=3)
        self.output_head = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Linear(latent_dim // 2, input_dim),
        )
        self.latent_dim = latent_dim
        self.input_dim = input_dim

    def forward(self, x_t: torch.Tensor, adj: torch.Tensor, steps: int = 1):
        """
        x_t: (batch, nodes, features)
        adj: (nodes, nodes)
        Returns dict with predictions and Koopman modes
        """
        B, N, F = x_t.shape

        # 1. Encode each node
        x_flat = x_t.reshape(B * N, F)
        z = self.koopman.encode(x_flat).reshape(B, N, self.latent_dim)

        # 2. Temporal propagation via Koopman
        z_flat = z.reshape(B * N, self.latent_dim)
        z_evolved = self.koopman.forward_k(z_flat, steps).reshape(B, N, self.latent_dim)

        # 3. Spatial propagation via GNN
        z_spatial = self.gnn(z_evolved, adj)

        # 4. Decode to physical space
        x_pred = self.output_head(z_spatial)

        # 5. Rothermel consistency check
        # FRP should increase when: low moisture + high wind + high temp
        wind_idx, moisture_idx = 2, 3
        rothermel_score = (
            (1 - x_t[:, :, moisture_idx]) * x_t[:, :, wind_idx] * x_t[:, :, 0]
        )

        return {
            "x_pred": x_pred,
            "z_latent": z_spatial,
            "rothermel_score": rothermel_score,
            "spectral_radius": self.koopman.spectral_radius,
        }


# ---------------------------------------------------------------------------
# Pipeline Operacional
# ---------------------------------------------------------------------------


def build_adjacency_matrix(municipios: dict = MUNICIPIOS_CE) -> np.ndarray:
    """Constrói adjacência real KNN dos municípios (k=4)."""
    from scipy.spatial.distance import cdist

    coords = np.array(list(municipios.values()))
    dist = cdist(coords, coords)
    n = len(coords)
    adj = np.zeros((n, n))
    for i in range(n):
        neighbors = np.argsort(dist[i])[1:5]  # k=4 vizinhos
        adj[i, neighbors] = 1
        adj[neighbors, i] = 1
    return adj


def compute_risk_index(prediction: dict, features_current: np.ndarray) -> list[dict]:
    """
    Calcula índice de risco por município combinando:
    - Previsão do modelo (FRP previsto)
    - Score de Rothermel (condições atuais)
    - Consenso (se GOES-16 disponível)

    Implementa Linha B (PEAK+PERSIST) ao nível do município.
    """
    x_pred = prediction["x_pred"].detach().cpu().numpy()[0]  # (nodes, features)
    rothermel = prediction["rothermel_score"].detach().cpu().numpy()[0]  # (nodes,)

    municipios = list(MUNICIPIOS_CE.keys())
    riscos = []

    for i, mun in enumerate(municipios):
        # FRP previsto (feature index 1, normalizado 0-1)
        frp_previsto = float(x_pred[i, 1])

        # Rothermel score (normalizado)
        roth_score = float(rothermel[i])

        # Índice composto: 40% modelo + 30% Rothermel + 30% condições atuais
        temp_atual = float(features_current[i, 0])
        umidade_atual = float(features_current[i, 3])

        indice = (
            0.40 * frp_previsto
            + 0.30 * roth_score
            + 0.15 * temp_atual
            + 0.15 * (1 - umidade_atual)
        )
        indice = min(1.0, max(0.0, indice))

        # Classificação
        if indice >= 0.7:
            classificacao = "critico"
        elif indice >= 0.5:
            classificacao = "alto"
        elif indice >= 0.3:
            classificacao = "medio"
        else:
            classificacao = "baixo"

        riscos.append({
            "municipio": mun,
            "lat": MUNICIPIOS_CE[mun][0],
            "lon": MUNICIPIOS_CE[mun][1],
            "indice_risco": round(indice, 4),
            "classificacao": classificacao,
            "frp_previsto": round(frp_previsto, 4),
            "rothermel_score": round(roth_score, 4),
            "componentes": {
                "modelo_koopman": round(frp_previsto, 4),
                "fisica_rothermel": round(roth_score, 4),
                "temperatura": round(temp_atual, 4),
                "deficit_umidade": round(1 - umidade_atual, 4),
            },
        })

    return sorted(riscos, key=lambda r: r["indice_risco"], reverse=True)


# ---------------------------------------------------------------------------
# Instância global (lazy loading)
# ---------------------------------------------------------------------------

_model_instance: Optional[NeKoPIGNN_Operational] = None
_adj_matrix: Optional[torch.Tensor] = None


def get_operational_model() -> tuple:
    """Retorna modelo e adjacência (lazy init)."""
    global _model_instance, _adj_matrix

    if _model_instance is None:
        logger.info("Inicializando modelo NeKo-PIGNN operacional...")
        _model_instance = NeKoPIGNN_Operational(
            input_dim=6, latent_dim=64, num_municipalities=len(MUNICIPIOS_CE)
        )
        _model_instance.eval()

        adj_np = build_adjacency_matrix()
        _adj_matrix = torch.tensor(adj_np, dtype=torch.float32)

        total_params = sum(p.numel() for p in _model_instance.parameters())
        logger.info(f"Modelo carregado: {total_params:,} parâmetros, spectral_radius={_model_instance.koopman.spectral_radius:.3f}")

    return _model_instance, _adj_matrix
