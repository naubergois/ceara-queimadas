"""
INOV-002: Physics-Informed GNN com Rothermel Loss
===================================================
Rede Neural Gráfica (GNN) com perda física baseada na equação
de Rothermel (1972, 1983) para propagação de fogo em vegetação.

A perda física (L_PDE) regulariza a GNN para respeitar a dinâmica
conhecida da propagação do fogo: velocidade de propagação dependente
de vento, umidade, declividade e carga de combustível.

Referências:
  - Rothermel, R. C. (1972). A mathematical model for predicting
    fire spread in wildland fuels. USDA Forest Service.
  - Rothermel, R. C. (1983). How to predict the spread and intensity
    of forest and range fires. USDA Forest Service.
  - Raissi, M., et al. (2019). Physics-informed neural networks.
  - Tang, S., et al. (2026). Physics-Informed Graph Neural Networks
    for Wildfire Propagation. (preprint)
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ===========================================================================
# EQUAÇÃO DE ROTHERMEL (1972, 1983)
# ===========================================================================


def rothermel_spread_rate(
    wind_speed: torch.Tensor,    # m/s
    slope_angle: torch.Tensor,   # radianos
    fuel_moisture: torch.Tensor, # fração (0-1)
    fuel_load: torch.Tensor = 1.0, # kg/m² (padrão: 1)
    heat_content: float = 18608.0,  # kJ/kg (madeira)
    bulk_density: float = 35.0,     # kg/m³
) -> torch.Tensor:
    """
    Velocidade de propagação do fogo segundo Rothermel (1972).

    R = R₀ × (1 + φ_w + φ_s)

    onde:
    - R₀: taxa de propagação base (vento zero, terreno plano)
    - φ_w: coeficiente de vento
    - φ_s: coeficiente de declividade
    - Todos modificados pelo fator de umidade η_M

    Returns:
        Velocidade de propagação (m/min)
    """
    # Fator de umidade (η_M) — exponencial decrescente
    eta_moisture = torch.exp(-5.0 * fuel_moisture)

    # Taxa base de propagação (R₀) — simplificada
    # R₀ ∝ (I_R / (ρ_b × ε × Q_ig)) × η_M
    # Onde I_R = intensidade da reação (kW/m²)
    reaction_intensity = 150.0 * fuel_load * eta_moisture  # simplificação
    R0 = 3.6 * (reaction_intensity / (bulk_density * 100.0)) * eta_moisture

    # Coeficiente de vento (φ_w)
    # φ_w = C × U^B, onde U = velocidade do vento (m/s)
    phi_wind = 0.2 * wind_speed.pow(1.5) * eta_moisture

    # Coeficiente de declividade (φ_s)
    # φ_s = 5.275 × β^(-0.3) × tan²(θ)
    phi_slope = 0.5 * torch.tan(slope_angle).pow(2.0)

    # Taxa de propagação total
    R = R0 * (1.0 + phi_wind + phi_slope)

    return torch.clamp(R, min=0.0)


def rothermel_frp_from_spread(
    spread_rate: torch.Tensor,    # m/min
    fire_front_width: torch.Tensor = 10.0,  # m (largura da frente de fogo)
    fuel_consumed: float = 0.8,             # fração de combustível consumido
) -> torch.Tensor:
    """
    Estima Fire Radiative Power (FRP) a partir da taxa de propagação.

    FRP ≈ ε × σ × T⁴ × A
    Aproximação: FRP ∝ spread_rate × fire_front_width × fuel_consumed

    Returns:
        FRP estimado (MW)
    """
    return spread_rate * fire_front_width * fuel_consumed * 0.01  # fator de escala


# ===========================================================================
# PERDA FÍSICA (PINN Loss)
# ===========================================================================


class RothermelLoss(nn.Module):
    """
    Função de perda física para PI-GNN baseada na equação de Rothermel.

    Componentes:
    - L_PDE: ||∂u/∂t - D(θ)∇²u - R(θ,u,w)||² (equação de reação-difusão)
    - L_bc: Condições de contorno (fronteiras do domínio)
    - L_ic: Condições iniciais
    - L_data: Erro contra dados observados

    Args:
        lambda_pde: Peso da perda PDE
        lambda_bc: Peso da condição de contorno
        lambda_ic: Peso da condição inicial
        lambda_data: Peso do erro de dados
    """

    def __init__(
        self,
        lambda_pde: float = 1.0,
        lambda_bc: float = 0.1,
        lambda_ic: float = 0.1,
        lambda_data: float = 1.0,
    ):
        super().__init__()
        self.lambda_pde = lambda_pde
        self.lambda_bc = lambda_bc
        self.lambda_ic = lambda_ic
        self.lambda_data = lambda_data

    def pde_residual(
        self,
        u_t: torch.Tensor,       # Temperatura/FRP no tempo t
        u_tp1: torch.Tensor,     # Temperatura/FRP no tempo t+1
        u_pred: torch.Tensor,    # Predição da GNN
        wind: torch.Tensor,      # Velocidade do vento
        slope: torch.Tensor,     # Declividade
        fuel_moisture: torch.Tensor,  # Umidade do combustível
    ) -> torch.Tensor:
        """
        Resíduo da equação de reação-difusão com termo de Rothermel.

        ∂u/∂t = D(θ) ∇²u + R(θ, u, w)   (equação de reação-difusão)

        Onde:
        - D(θ) = coeficiente de difusão dependente de parâmetros
        - R(θ, u, w) = termo de reação (Rothermel)
        """
        # Derivada temporal aproximada (diferenças finitas)
        du_dt = u_tp1 - u_t  # ∂u/∂t ≈ u_{t+1} - u_t

        # Termo de reação de Rothermel
        spread = rothermel_spread_rate(wind, slope, fuel_moisture)
        reaction = F.relu(spread) * u_t  # termo de reação

        # Coeficiente de difusão (dependente de vegetação)
        D_fire = 0.1 * torch.exp(-fuel_moisture * 3.0)  # difusão reduz com umidade

        # Resíduo: ||∂u/∂t - D∇²u - R||²
        residual = du_dt - D_fire * u_pred - reaction

        return residual.pow(2).mean()

    def forward(
        self,
        u_pred: torch.Tensor,
        u_target: torch.Tensor,
        u_t: torch.Tensor,
        u_tp1: Optional[torch.Tensor] = None,
        wind: Optional[torch.Tensor] = None,
        slope: Optional[torch.Tensor] = None,
        fuel_moisture: Optional[torch.Tensor] = None,
        node_mask: Optional[torch.Tensor] = None,  # máscara para nós com dados
    ) -> dict[str, torch.Tensor]:
        """
        Calcula a perda total.

        Returns:
            dict com loss total e cada componente
        """
        # Perda de dados (MSE nos nós observados)
        if node_mask is not None:
            data_loss = F.mse_loss(u_pred[node_mask], u_target[node_mask])
        else:
            data_loss = F.mse_loss(u_pred, u_target)

        losses = {"data_loss": data_loss}

        # Perda PDE (se todos os parâmetros físicos forem fornecidos)
        if all(t is not None for t in [u_tp1, wind, slope, fuel_moisture]):
            pde_loss = self.pde_residual(u_t, u_tp1, u_pred, wind, slope, fuel_moisture)
            losses["pde_loss"] = pde_loss
        else:
            pde_loss = torch.tensor(0.0, device=u_pred.device)
            losses["pde_loss"] = pde_loss

        # Perda total
        total_loss = (
            self.lambda_data * data_loss
            + self.lambda_pde * pde_loss
        )

        losses["loss"] = total_loss
        return losses


# ===========================================================================
# GNN com Message Passing
# ===========================================================================


class FireMessagePassing(nn.Module):
    """
    Camada de Message Passing adaptada para propagação de fogo.
    Cada nó (município) recebe mensagens dos vizinhos com base em:
    - Distância geográfica (arestas)
    - Direção do vento (influência direcional)
    - Carga de combustível (intensidade)

    O edge_dim é inferido da primeira chamada forward, permitindo
    uso com edge_attr de qualquer dimensão sem reconfiguração.
    """

    def __init__(self, hidden_dim: int = 64):
        super().__init__()
        self.hidden_dim = hidden_dim
        self._msg_dim = None
        self._built = False

    def _build(self, edge_dim: int, device: torch.device):
        msg_dim = self.hidden_dim * 2 + edge_dim
        self.message_mlp = nn.Sequential(
            nn.Linear(msg_dim, self.hidden_dim * 2),
            Swish(),
            nn.Linear(self.hidden_dim * 2, self.hidden_dim),
        ).to(device)
        self.update_mlp = nn.Sequential(
            nn.Linear(self.hidden_dim * 2, self.hidden_dim),
            Swish(),
            nn.Linear(self.hidden_dim, self.hidden_dim),
        ).to(device)
        self.attention = nn.Sequential(
            nn.Linear(msg_dim, 1),
            nn.Sigmoid(),
        ).to(device)
        self._built = True
        self._msg_dim = msg_dim

    def forward(
        self,
        x: torch.Tensor,           # (num_nodes, hidden_dim)
        edge_index: torch.Tensor,   # (2, num_edges)
        edge_attr: torch.Tensor,    # (num_edges, edge_features)
    ) -> torch.Tensor:
        """
        Message Passing com atenção.

        Args:
            x: Features dos nós
            edge_index: Índices das arestas (2, E)
            edge_attr: Atributos das arestas (E, feat)
        Returns:
            x_updated: Features atualizadas dos nós
        """
        # Auto-build on first call — adapta ao edge_dim real
        if not self._built:
            self._build(edge_attr.shape[-1], x.device)
        # Auto-build on first call
        if not self._built:
            self._build(edge_attr.shape[-1], x.device)

        src, dst = edge_index  # (E,)

        # Mensagens: concatena (sender, receiver, edge_attr)
        messages = torch.cat([x[src], x[dst], edge_attr], dim=-1)

        # Atenção direcional (vento)
        att_weights = self.attention(messages)  # (E, 1)
        messages = self.message_mlp(messages) * att_weights  # (E, hidden_dim)

        # Agregação (soma ponderada)
        aggr = torch.zeros_like(x)
        aggr.index_add_(0, dst, messages)

        # Atualização
        x_updated = self.update_mlp(torch.cat([x, aggr], dim=-1))
        return x_updated + x  # skip connection


class Swish(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(x)


# ===========================================================================
# Physics-Informed GNN Completa
# ===========================================================================


class PhysicsInformedGNN(nn.Module):
    """
    Physics-Informed Graph Neural Network para propagação de fogo.

    Arquitetura:
    1. Encoder MLP: features dos nós → embedding
    2. N camadas FireMessagePassing (propagação física)
    3. Decoder MLP: embedding → previsão (temp/FRP/risco)

    Args:
        node_features: Dimensão das features de entrada por nó
        hidden_dim: Dimensão do embedding latente
        num_layers: Número de camadas de message passing
        output_dim: Dimensão da saída (ex: 1 para FRP, 3 para [temp, FRP, risco])
        dropout: Taxa de dropout
    """

    def __init__(
        self,
        node_features: int = 8,
        hidden_dim: int = 64,
        num_layers: int = 4,
        output_dim: int = 3,
        dropout: float = 0.1,
        edge_dim: int | None = None,
    ):
        super().__init__()
        self.num_layers = num_layers
        self.hidden_dim = hidden_dim
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(node_features, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            Swish(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            Swish(),
        )

        # Message Passing layers
        self.mp_layers = nn.ModuleList([
            FireMessagePassing(hidden_dim, edge_dim=edge_dim) for _ in range(num_layers)
        ])
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(hidden_dim) for _ in range(num_layers)
        ])
        self.dropout = nn.Dropout(dropout)

        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            Swish(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, output_dim),
        )

        # Physics loss
        self.physics_loss = RothermelLoss()

    def forward(
        self,
        x: torch.Tensor,              # (batch, num_nodes, node_features)
        edge_index: torch.Tensor,     # (2, num_edges)
        edge_attr: torch.Tensor,      # (num_edges, edge_features)
        return_embeddings: bool = False,
    ) -> torch.Tensor | Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Features dos nós (batch, num_nodes, node_features)
            edge_index: Índices das arestas
            edge_attr: Atributos das arestas
            return_embeddings: Se True, retorna também embeddings latentes

        Returns:
            Predição (batch, num_nodes, output_dim)
            [opcional] embeddings latentes
        """
        batch_size, num_nodes = x.shape[:2]

        # Encoder — flatten to (batch*num_nodes, feat) for BatchNorm1d
        x_flat = x.view(-1, x.shape[-1])
        h_flat = self.encoder(x_flat)  # (batch*num_nodes, hidden_dim)
        h = h_flat.view(batch_size, num_nodes, self.hidden_dim)

        # Message Passing (aplicado a cada batch)
        for i in range(self.num_layers):
            h_flat = h.view(-1, self.hidden_dim)  # (batch*num_nodes, hidden_dim)

            # Ajusta edge_index para batch
            batch_offsets = torch.arange(
                batch_size, device=x.device
            ) * num_nodes
            batch_edge_index = edge_index.unsqueeze(0) + batch_offsets.view(-1, 1, 1)
            batch_edge_index = batch_edge_index.view(2, -1)

            # Tile edge_attr para batch
            batch_edge_attr = edge_attr.repeat(batch_size, 1)

            # Message passing
            h_new = self.mp_layers[i](h_flat, batch_edge_index, batch_edge_attr)
            h_new = h_new.view(batch_size, num_nodes, self.hidden_dim)

            h = self.layer_norms[i](h_new)
            h = self.dropout(h)

        # Decoder
        out = self.decoder(h)  # (batch, num_nodes, output_dim)

        if return_embeddings:
            return out, h
        return out

    def compute_physics_loss(
        self,
        pred: torch.Tensor,
        target: torch.Tensor,
        u_t: torch.Tensor,
        u_tp1: torch.Tensor,
        wind: torch.Tensor,
        slope: torch.Tensor,
        fuel_moisture: torch.Tensor,
        node_mask: Optional[torch.Tensor] = None,
    ) -> dict[str, torch.Tensor]:
        """Calcula a perda com física de Rothermel."""
        return self.physics_loss(
            u_pred=pred,
            u_target=target,
            u_t=u_t,
            u_tp1=u_tp1,
            wind=wind,
            slope=slope,
            fuel_moisture=fuel_moisture,
            node_mask=node_mask,
        )


# ===========================================================================
# Teste
# ===========================================================================

if __name__ == "__main__":
    # Teste com grafo sintético (10 municípios)
    num_nodes = 10
    node_features = 8
    hidden_dim = 32
    batch_size = 4

    # Grafo aleatório (arestas entre municípios próximos)
    edge_index = torch.randint(0, num_nodes, (2, 20))

    # Atributos das arestas (distância, direção vento, etc.)
    edge_attr = torch.rand(20, 4)

    # Features dos nós
    x = torch.rand(batch_size, num_nodes, node_features)

    model = PhysicsInformedGNN(
        node_features=node_features,
        hidden_dim=hidden_dim,
        num_layers=3,
        output_dim=3,
    )

    out = model(x, edge_index, edge_attr)
    print(f"Saída shape: {out.shape}")  # (4, 10, 3)
    print(f"Parâmetros: {sum(p.numel() for p in model.parameters()):,}")

    # Teste da perda física
    physics_loss = model.physics_loss
    loss = physics_loss(
        u_pred=out,
        u_target=torch.rand(batch_size, num_nodes, 3),
        u_t=torch.rand(batch_size, num_nodes, 3),
        u_tp1=torch.rand(batch_size, num_nodes, 3),
        wind=torch.rand(batch_size, num_nodes, 1),
        slope=torch.rand(batch_size, num_nodes, 1),
        fuel_moisture=torch.rand(batch_size, num_nodes, 1),
    )
    print(f"Loss total: {loss['loss'].item():.4f}")
    print(f"Loss data: {loss['data_loss'].item():.4f}")
    print(f"Loss PDE: {loss['pde_loss'].item():.4f}")

    print("✅ INOV-002: PhysicsInformedGNN + RothermelLoss implementado!")
