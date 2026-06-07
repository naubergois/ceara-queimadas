"""
INOV-001: Neural Koopman Operator para Dinâmica de Queimadas
=============================================================
Implementa o operador de Koopman neural com autoencoder variacional
para linearização da dinâmica de propagação do fogo.

Referências:
  - Brunton, S. L., et al. (2021). Data-Driven Science and Engineering.
  - Williams, M. O., et al. (2015). A Data-Driven Approximation of the
    Koopman Operator: Extended Dynamic Mode Decomposition.
  - Lusch, B., et al. (2018). Deep learning for universal linear
    embeddings of nonlinear dynamics.

Arquitetura:
  Encoder: estado físico → observáveis de Koopman (g(z))
  Matriz K: evolução linear no espaço latente (Koopman)
  Decoder: observáveis → estado físico reconstruído
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


def _check_device(device: Optional[str] = None) -> torch.device:
    if device is not None:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Blocos do Autoencoder Variacional
# ---------------------------------------------------------------------------


class Swish(nn.Module):
    """Ativação Swish (SiLU) — suave, não monótona, boa para PINNs."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(x)


class EncoderMLP(nn.Module):
    """Encoder: estado físico (R^d) → observáveis latentes (R^p)."""

    def __init__(
        self,
        input_dim: int = 6,
        latent_dim: int = 32,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [64, 128, 64]

        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers.extend([
                nn.Linear(prev, h),
                nn.BatchNorm1d(h),
                Swish(),
                nn.Dropout(dropout),
            ])
            prev = h
        self.backbone = nn.Sequential(*layers)

        # Cabeças para média e log-variância (VAE)
        self.mu = nn.Linear(prev, latent_dim)
        self.log_var = nn.Linear(prev, latent_dim)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h = self.backbone(x)
        return self.mu(h), self.log_var(h)


class DecoderMLP(nn.Module):
    """Decoder: observáveis latentes (R^p) → estado físico (R^d)."""

    def __init__(
        self,
        latent_dim: int = 32,
        output_dim: int = 6,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [64, 128, 64]

        layers = []
        prev = latent_dim
        for h in hidden_dims:
            layers.extend([
                nn.Linear(prev, h),
                nn.BatchNorm1d(h),
                Swish(),
                nn.Dropout(dropout),
            ])
            prev = h
        layers.append(nn.Linear(prev, output_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return self.net(z)


# ---------------------------------------------------------------------------
# Operador de Koopman Neural (VAE + Matriz K)
# ---------------------------------------------------------------------------


class NeuralKoopmanOperator(nn.Module):
    """
    Operador de Koopman Neural com VAE.

    Formulação:
        g(z_t) = encoder(z_t)
        g(z_{t+1}) = K @ g(z_t)    [propagação linear no espaço latente]
        z_{t+1} = decoder(g(z_{t+1}))

    Perda total:
        L = L_recon + β * L_KL + α * L_pred + λ * L_phys

    Args:
        input_dim: Dimensão do estado físico (ex: 6: temp, frp, vento, umidade, ndvi, declividade)
        latent_dim: Dimensão do espaço de observáveis de Koopman
        koopman_rank: Rank da matriz K (se < latent_dim, fatoração baixo posto)
        beta: Peso do termo KL (β-VAE)
        alpha: Peso do termo de predição (forward loss)
        lambda_phys: Peso da regularização física (se > 0, ativa PINN)
    """

    def __init__(
        self,
        input_dim: int = 6,
        latent_dim: int = 32,
        koopman_rank: int = 16,
        beta: float = 0.1,
        alpha: float = 1.0,
        lambda_phys: float = 0.0,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.koopman_rank = koopman_rank
        self.beta = beta
        self.alpha = alpha
        self.lambda_phys = lambda_phys

        self.encoder = EncoderMLP(input_dim, latent_dim, hidden_dims, dropout)
        self.decoder = DecoderMLP(latent_dim, input_dim, hidden_dims, dropout)

        # Matriz de Koopman K ∈ R^(latent_dim × latent_dim)
        # Usar fatoração de baixo posto para regularização
        self.U_koopman = nn.Parameter(
            torch.randn(latent_dim, koopman_rank) * 0.01
        )
        self.V_koopman = nn.Parameter(
            torch.randn(koopman_rank, latent_dim) * 0.01
        )

        # Bias
        self.bias = nn.Parameter(torch.zeros(latent_dim))

    @property
    def K_matrix(self) -> torch.Tensor:
        """Matriz K = U @ V (baixo posto) + regularização diagonal."""
        return self.U_koopman @ self.V_koopman  # (latent_dim, latent_dim)

    def encode(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Codifica x → mu, log_var, z (amostrado com reparameterization trick)."""
        mu, log_var = self.encoder(x)
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        z = mu + eps * std
        return mu, log_var, z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decodifica z → x_recon."""
        return self.decoder(z)

    def forward_koopman(self, z: torch.Tensor, steps: int = 1) -> torch.Tensor:
        """
        Propaga z no espaço de Koopman por `steps` passos.
        z_{t+n} = K^n @ z_t + Σ_{i=0}^{n-1} K^i @ bias
        """
        K = self.K_matrix
        z_out = z
        for _ in range(steps):
            z_out = z_out @ K.T + self.bias
        return z_out

    def forward(
        self, x_t: torch.Tensor, x_tp1: Optional[torch.Tensor] = None
    ) -> dict[str, torch.Tensor]:
        """
        Forward pass.

        Args:
            x_t: Estado no tempo t (batch, input_dim)
            x_tp1: Estado no tempo t+1 (opcional, para treino)

        Returns:
            dict com chaves: z_t, x_recon, x_pred, x_tp1 (se fornecido),
                             mu, log_var, loss (se x_tp1 fornecido)
        """
        # Codifica
        mu, log_var, z_t = self.encode(x_t)
        x_recon = self.decode(z_t)

        # Propagação Koopman
        z_tp1 = self.forward_koopman(z_t, steps=1)
        x_pred = self.decode(z_tp1)

        result = {
            "z_t": z_t,
            "x_recon": x_recon,
            "x_pred": x_pred,
            "mu": mu,
            "log_var": log_var,
        }

        if x_tp1 is not None:
            # Perda de reconstrução
            recon_loss = F.mse_loss(x_recon, x_t)

            # Perda KL divergência
            kl_loss = -0.5 * torch.sum(1 + log_var - mu.pow(2) - log_var.exp())
            kl_loss = kl_loss / x_t.size(0)  # normalizar por batch

            # Perda de predição (Koopman)
            pred_loss = F.mse_loss(x_pred, x_tp1)

            # Perda total
            loss = recon_loss + self.beta * kl_loss + self.alpha * pred_loss

            # Regularização física (se ativada)
            if self.lambda_phys > 0:
                phys_loss = self._physical_regularization(x_t, x_pred)
                loss = loss + self.lambda_phys * phys_loss
                result["phys_loss"] = phys_loss

            result.update({
                "loss": loss,
                "recon_loss": recon_loss,
                "kl_loss": kl_loss,
                "pred_loss": pred_loss,
            })

        return result

    def _physical_regularization(
        self, x_t: torch.Tensor, x_pred: torch.Tensor
    ) -> torch.Tensor:
        """
        Regularização física simples:
        - Temperatura não deve crescer indefinidamente sem combustível
        - FRP deve ser positivo
        - Suavidade temporal
        """
        # Penalidade para FRP negativo
        frp_pred = x_pred[:, 1]  # assumindo FRP no índice 1
        frp_penalty = torch.relu(-frp_pred).mean()

        # Suavidade: diferença pequena entre t e t+1
        smoothness = F.mse_loss(x_pred, x_t)

        return frp_penalty + 0.1 * smoothness


# ---------------------------------------------------------------------------
# Treinamento
# ---------------------------------------------------------------------------


def train_koopman(
    model: NeuralKoopmanOperator,
    train_loader: torch.utils.data.DataLoader,
    val_loader: Optional[torch.utils.data.DataLoader] = None,
    epochs: int = 100,
    lr: float = 1e-3,
    weight_decay: float = 1e-5,
    device: Optional[torch.device] = None,
    verbose: bool = True,
) -> dict[str, list[float]]:
    """
    Treina o NeuralKoopmanOperator.

    Args:
        model: Modelo a treinar
        train_loader: DataLoader com tuplas (x_t, x_tp1)
        val_loader: DataLoader opcional de validação
        epochs: Número de épocas
        lr: Learning rate
        weight_decay: Regularização L2
        device: Dispositivo (auto-detect se None)
        verbose: Print progresso

    Returns:
        dict com histórico de loss (train_loss, val_loss)
    """
    device = _check_device(device)
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "recon_loss": [],
        "pred_loss": [],
        "kl_loss": [],
    }

    for epoch in range(epochs):
        model.train()
        train_losses = {"loss": 0.0, "recon": 0.0, "pred": 0.0, "kl": 0.0}
        n_batches = 0

        for batch in train_loader:
            x_t, x_tp1 = batch
            x_t = x_t.to(device)
            x_tp1 = x_tp1.to(device)

            optimizer.zero_grad()
            outputs = model(x_t, x_tp1)
            loss = outputs["loss"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_losses["loss"] += outputs["loss"].item()
            train_losses["recon"] += outputs["recon_loss"].item()
            train_losses["pred"] += outputs["pred_loss"].item()
            train_losses["kl"] += outputs["kl_loss"].item()
            n_batches += 1

        scheduler.step()

        avg_train = {k: v / n_batches for k, v in train_losses.items()}
        history["train_loss"].append(avg_train["loss"])
        history["recon_loss"].append(avg_train["recon"])
        history["pred_loss"].append(avg_train["pred"])
        history["kl_loss"].append(avg_train["kl"])

        # Validação
        if val_loader:
            model.eval()
            val_loss = 0.0
            n_val = 0
            with torch.no_grad():
                for batch in val_loader:
                    x_t, x_tp1 = batch
                    x_t = x_t.to(device)
                    x_tp1 = x_tp1.to(device)
                    outputs = model(x_t, x_tp1)
                    val_loss += outputs["loss"].item()
                    n_val += 1
            history["val_loss"].append(val_loss / n_val) if n_val > 0 else history["val_loss"].append(0.0)

        if verbose and (epoch + 1) % 10 == 0:
            log = f"[{epoch+1}/{epochs}] loss={avg_train['loss']:.4f} "
            log += f"recon={avg_train['recon']:.4f} pred={avg_train['pred']:.4f} kl={avg_train['kl']:.4f}"
            if history["val_loss"]:
                log += f" val={history['val_loss'][-1]:.4f}"
            print(log)

    return history


# ---------------------------------------------------------------------------
# Teste rápido
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Teste com dados sintéticos
    batch_size = 32
    input_dim = 6
    seq_len = 10

    # Simula série temporal
    t = torch.linspace(0, 4 * math.pi, seq_len)
    x_synth = torch.stack([
        torch.sin(t) + 0.1 * torch.randn(seq_len),   # temp
        0.5 * (torch.sin(t) + 1) + 0.05 * torch.randn(seq_len),  # frp
        0.3 * torch.sin(2 * t) + 0.1 * torch.randn(seq_len),     # vento
        0.4 + 0.1 * torch.randn(seq_len),                          # umidade
        0.6 + 0.05 * torch.randn(seq_len),                        # ndvi
        0.2 * torch.sin(t) + 0.05 * torch.randn(seq_len),         # declividade
    ], dim=1).T  # (seq_len, input_dim)

    dataset = torch.utils.data.TensorDataset(x_synth[:-1], x_synth[1:])
    loader = torch.utils.data.DataLoader(dataset, batch_size=4, shuffle=True)

    model = NeuralKoopmanOperator(
        input_dim=input_dim,
        latent_dim=16,
        koopman_rank=8,
        beta=0.1,
        alpha=1.0,
    )

    print(f"Modelo: {sum(p.numel() for p in model.parameters()):,} parâmetros")
    print(f"Matriz K shape: {model.K_matrix.shape}")

    history = train_koopman(model, loader, epochs=50, verbose=True)
    print(f"Loss final: {history['train_loss'][-1]:.4f}")
    print("✅ INOV-001: NeuralKoopmanOperator implementado e testado com dados sintéticos!")
