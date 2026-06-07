"""
INOV-003: NeKo-PIGNN — Modelo Híbrido Koopman + PI-GNN
=========================================================
Unifica o Neural Koopman Operator (INOV-001) com a Physics-Informed GNN
(INOV-002) para criar o modelo híbrido completo:

  1. Koopman no espaço latente (observáveis aprendidos)
  2. PI-GNN regulariza a matriz K com física de Rothermel
  3. GNN propaga estado entre nós (municípios vizinhos)

Arquitetura:
  Dados VIIRS → [Koopman Autoencoder] → Espaço Latente (g(z))
                                      → [PI-GNN] → Propagação entre nós
                                      → [Rothermel Loss] → Regularização física
  Saída: Previsão temporal de focos/FRP por município

Este é o coração matemático do artigo A1:
  "Neural Koopman Operator + Physics-Informed Graph Neural Networks
   for Real-Time Wildfire Digital Twin"

Referências:
  - Brunton (2021), Raissi (2019), Rothermel (1972), Tang (2026)
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from .koopman_operator import NeuralKoopmanOperator
from .pignn import PhysicsInformedGNN, RothermelLoss


class NeKoPIGNN(nn.Module):
    """
    Modelo Híbrido Neural Koopman + Physics-Informed GNN.

    Fluxo:
    1. Cada nó tem seu estado físico (temp, FRP, vento, umidade, etc.)
    2. Koopman: codifica cada nó para espaço latente e propaga no tempo
    3. GNN: propaga informação entre nós vizinhos
    4. Perda: L = L_recon + L_pred + L_KL + L_PDE + L_GNN

    Args:
        node_features: Features físicas por nó
        latent_dim: Dimensão do espaço de Koopman
        gnn_hidden: Dimensão oculta da GNN
        num_nodes: Número de nós (municípios)
        koopman_rank: Rank da matriz K
        beta: Peso KL no VAE
        alpha: Peso da predição Koopman
        lambda_pde: Peso da perda PDE (Rothermel)
        lambda_gnn: Peso da perda GNN
    """

    def __init__(
        self,
        node_features: int = 8,
        latent_dim: int = 32,
        gnn_hidden: int = 64,
        num_nodes: int = 184,
        koopman_rank: int = 16,
        beta: float = 0.1,
        alpha: float = 1.0,
        lambda_pde: float = 0.5,
        lambda_gnn: float = 1.0,
    ):
        super().__init__()
        self.node_features = node_features
        self.latent_dim = latent_dim
        self.num_nodes = num_nodes

        # Koopman Operator (por nó)
        self.koopman = NeuralKoopmanOperator(
            input_dim=node_features,
            latent_dim=latent_dim,
            koopman_rank=koopman_rank,
            beta=beta,
            alpha=alpha,
        )

        # GNN para propagação entre nós no espaço latente
        self.gnn = PhysicsInformedGNN(
            node_features=latent_dim,  # entrada = observáveis de Koopman
            hidden_dim=gnn_hidden,
            num_layers=3,
            output_dim=latent_dim,     # saída = observáveis atualizados
        )

        # Decoder para saída física
        self.output_decoder = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.BatchNorm1d(num_nodes),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(latent_dim // 2, node_features),
        )

        # Perda física
        self.physics_loss = RothermelLoss()

        # Parâmetros de perda
        self.lambda_pde = lambda_pde
        self.lambda_gnn = lambda_gnn

    def forward(
        self,
        x_t: torch.Tensor,              # (batch, num_nodes, node_features) no tempo t
        x_tp1: Optional[torch.Tensor] = None,  # (batch, num_nodes, node_features) no tempo t+1
        edge_index: Optional[torch.Tensor] = None,  # (2, E)
        edge_attr: Optional[torch.Tensor] = None,   # (E, edge_feat)
        wind: Optional[torch.Tensor] = None,
        slope: Optional[torch.Tensor] = None,
        fuel_moisture: Optional[torch.Tensor] = None,
    ) -> dict[str, torch.Tensor]:
        """
        Forward pass do modelo híbrido.

        Args:
            x_t: Estado em t (batch, num_nodes, features)
            x_tp1: Estado em t+1 (para treino)
            edge_index: Arestas do grafo
            edge_attr: Atributos das arestas
            wind: Velocidade do vento (para physical loss)
            slope: Declividade (para physical loss)
            fuel_moisture: Umidade do combustível (para physical loss)

        Returns:
            dict com saídas e perdas
        """
        batch_size, num_nodes, n_feat = x_t.shape
        device = x_t.device

        # === 1. Koopman: codificar cada nó ===
        # Achata para processar todos os nós de uma vez
        x_flat = x_t.view(-1, n_feat)  # (batch*num_nodes, features)

        # Codifica
        mu, log_var, z_t = self.koopman.encode(x_flat)
        x_recon = self.koopman.decode(z_t)
        x_recon = x_recon.view(batch_size, num_nodes, n_feat)

        # Propaga no tempo via Koopman (independente por nó)
        z_tp1_koopman = self.koopman.forward_koopman(z_t, steps=1)
        z_tp1_koopman = z_tp1_koopman.view(batch_size, num_nodes, self.latent_dim)

        # === 2. GNN: propagação entre nós no espaço latente ===
        if edge_index is not None and edge_attr is not None:
            z_tp1_gnn = self.gnn(
                z_tp1_koopman,  # entrada = Koopman propagado + batch
                edge_index,
                edge_attr,
            )  # (batch, num_nodes, latent_dim)
        else:
            z_tp1_gnn = z_tp1_koopman

        # === 3. Decodificar para estado físico ===
        z_flat = z_tp1_gnn.view(-1, self.latent_dim)
        x_pred = self.output_decoder(z_flat)
        x_pred = x_pred.view(batch_size, num_nodes, n_feat)

        result = {
            "x_recon": x_recon,
            "x_pred": x_pred,
            "z_t": z_t.view(batch_size, num_nodes, self.latent_dim),
            "z_tp1": z_tp1_gnn,
            "mu": mu.view(batch_size, num_nodes, -1),
            "log_var": log_var.view(batch_size, num_nodes, -1),
        }

        # === 4. Perdas (apenas em treino) ===
        if x_tp1 is not None:
            # Perda de reconstrução Koopman
            recon_loss = F.mse_loss(x_recon, x_t)

            # Perda KL
            kl_loss = -0.5 * torch.sum(
                1 + log_var - mu.pow(2) - log_var.exp()
            ) / (batch_size * num_nodes)

            # Perda de predição (via Koopman + GNN)
            pred_loss = F.mse_loss(x_pred, x_tp1)

            # Perda GNN (consistência espaço latente)
            gnn_loss = F.mse_loss(z_tp1_gnn, z_tp1_koopman)

            loss = recon_loss + self.koopman.beta * kl_loss + self.koopman.alpha * pred_loss + self.lambda_gnn * gnn_loss

            # Perda PDE (Rothermel) — se parâmetros físicos fornecidos
            if all(t is not None for t in [wind, slope, fuel_moisture]):
                pde_losses = self.physics_loss(
                    u_pred=x_pred,
                    u_target=x_tp1,
                    u_t=x_t,
                    u_tp1=x_tp1,
                    wind=wind,
                    slope=slope,
                    fuel_moisture=fuel_moisture,
                )
                pde_loss = pde_losses["pde_loss"]
                loss = loss + self.lambda_pde * pde_loss
                result["pde_loss"] = pde_loss

            result.update({
                "loss": loss,
                "recon_loss": recon_loss,
                "kl_loss": kl_loss,
                "pred_loss": pred_loss,
                "gnn_loss": gnn_loss,
            })

        return result


# ===========================================================================
# Treinamento
# ===========================================================================


def train_neko_pignn(
    model: NeKoPIGNN,
    train_loader: torch.utils.data.DataLoader,
    val_loader: Optional[torch.utils.data.DataLoader] = None,
    epochs: int = 150,
    lr: float = 5e-4,
    weight_decay: float = 1e-5,
    device: Optional[torch.device] = None,
    verbose: bool = True,
) -> dict[str, list[float]]:
    """
    Treina o modelo híbrido NeKo-PIGNN.

    Args:
        model: Modelo a treinar
        train_loader: DataLoader com tuplas (x_t, x_tp1, edge_index, edge_attr, physics_params)
        val_loader: DataLoader de validação
        epochs: Número de épocas
        lr: Learning rate
        weight_decay: Regularização L2
        device: Dispositivo
        verbose: Print progresso

    Returns:
        dict com histórico de perdas
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=10, min_lr=1e-6
    )

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "recon_loss": [],
        "pred_loss": [],
        "kl_loss": [],
        "gnn_loss": [],
    }

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        total_recon = 0.0
        total_pred = 0.0
        total_kl = 0.0
        total_gnn = 0.0
        n_batches = 0

        for batch in train_loader:
            # Desempacota batch
            x_t, x_tp1 = batch[0].to(device), batch[1].to(device)
            edge_index = batch[2].to(device) if len(batch) > 2 else None
            edge_attr = batch[3].to(device) if len(batch) > 3 else None
            wind = batch[4].to(device) if len(batch) > 4 else None
            slope = batch[5].to(device) if len(batch) > 5 else None
            fuel_moisture = batch[6].to(device) if len(batch) > 6 else None

            optimizer.zero_grad()
            outputs = model(
                x_t, x_tp1=x_tp1,
                edge_index=edge_index,
                edge_attr=edge_attr,
                wind=wind,
                slope=slope,
                fuel_moisture=fuel_moisture,
            )
            loss = outputs["loss"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += outputs["loss"].item()
            total_recon += outputs.get("recon_loss", torch.tensor(0.0)).item()
            total_pred += outputs.get("pred_loss", torch.tensor(0.0)).item()
            total_kl += outputs.get("kl_loss", torch.tensor(0.0)).item()
            total_gnn += outputs.get("gnn_loss", torch.tensor(0.0)).item()
            n_batches += 1

        avg = {
            "loss": total_loss / n_batches,
            "recon": total_recon / n_batches,
            "pred": total_pred / n_batches,
            "kl": total_kl / n_batches,
            "gnn": total_gnn / n_batches,
        }
        history["train_loss"].append(avg["loss"])
        history["recon_loss"].append(avg["recon"])
        history["pred_loss"].append(avg["pred"])
        history["kl_loss"].append(avg["kl"])
        history["gnn_loss"].append(avg["gnn"])

        # Validação
        if val_loader:
            model.eval()
            val_loss = 0.0
            n_val = 0
            with torch.no_grad():
                for batch in val_loader:
                    x_t, x_tp1 = batch[0].to(device), batch[1].to(device)
                    edge_index = batch[2].to(device) if len(batch) > 2 else None
                    edge_attr = batch[3].to(device) if len(batch) > 3 else None
                    outputs = model(x_t, x_tp1=x_tp1, edge_index=edge_index, edge_attr=edge_attr)
                    val_loss += outputs["loss"].item()
                    n_val += 1
            history["val_loss"].append(val_loss / n_val)
            scheduler.step(val_loss / n_val)
        else:
            scheduler.step(avg["loss"])

        if verbose and (epoch + 1) % 15 == 0:
            log = f"[{epoch+1}/{epochs}] loss={avg['loss']:.4f} rec={avg['recon']:.4f} pred={avg['pred']:.4f} kl={avg['kl']:.4f} gnn={avg['gnn']:.4f}"
            if history["val_loss"]:
                log += f" val={history['val_loss'][-1]:.4f}"
            print(log)

    return history


# ===========================================================================
# Utilitário: criar grafo dos municípios do Ceará
# ===========================================================================


def build_ceara_graph(
    num_nodes: int = 184,
    knn: int = 5,
    noise: float = 0.1,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Constrói um grafo KNN simulado dos municípios do Ceará.
    (Substituir por dados reais de coordenadas geográficas.)

    Args:
        num_nodes: Número de municípios (CE tem 184)
        knn: K vizinhos mais próximos
        noise: Ruído posicional

    Returns:
        edge_index: (2, E)
        edge_attr: (E, 3) [distância, direção_x, direção_y]
    """
    # Coordenadas simuladas (substituir por lat/lon reais)
    coords = torch.randn(num_nodes, 2) * noise

    # Matriz de distância
    dist = torch.cdist(coords, coords)

    # KNN
    _, indices = torch.topk(dist, k=knn + 1, dim=1, largest=False)
    indices = indices[:, 1:]  # remove self-loop

    # Edge index
    src = torch.arange(num_nodes).unsqueeze(1).expand(-1, knn).reshape(-1)
    dst = indices.reshape(-1)
    edge_index = torch.stack([src, dst], dim=0)

    # Edge attributes (distância e direção normalizada)
    edge_dist = dist[src, dst].unsqueeze(1)
    direction = coords[dst] - coords[src]
    edge_attr = torch.cat([edge_dist, direction], dim=1)

    return edge_index, edge_attr


# ===========================================================================
# Teste
# ===========================================================================

if __name__ == "__main__":
    batch_size = 4
    num_nodes = 10  # pequeno para teste
    node_features = 6
    latent_dim = 16

    # Dados sintéticos
    x_t = torch.randn(batch_size, num_nodes, node_features)
    x_tp1 = torch.randn(batch_size, num_nodes, node_features)

    # Grafo
    edge_index, edge_attr = build_ceara_graph(num_nodes=num_nodes, knn=3, noise=0.5)

    # Parâmetros físicos
    wind = torch.rand(batch_size, num_nodes, 1)
    slope = torch.rand(batch_size, num_nodes, 1)
    fuel_moisture = torch.rand(batch_size, num_nodes, 1)

    model = NeKoPIGNN(
        node_features=node_features,
        latent_dim=latent_dim,
        gnn_hidden=32,
        num_nodes=num_nodes,
        koopman_rank=8,
    )

    total_params = sum(p.numel() for p in model.parameters())
    print(f"NeKo-PIGNN parâmetros: {total_params:,}")

    outputs = model(
        x_t, x_tp1=x_tp1,
        edge_index=edge_index,
        edge_attr=edge_attr,
        wind=wind,
        slope=slope,
        fuel_moisture=fuel_moisture,
    )

    print(f"Loss: {outputs['loss'].item():.4f}")
    print(f"Recon: {outputs['recon_loss'].item():.4f}")
    print(f"Pred: {outputs['pred_loss'].item():.4f}")
    print(f"KL: {outputs['kl_loss'].item():.4f}")
    print(f"GNN: {outputs['gnn_loss'].item():.4f}")

    print("✅ INOV-003: NeKo-PIGNN implementado e testado com dados sintéticos!")
