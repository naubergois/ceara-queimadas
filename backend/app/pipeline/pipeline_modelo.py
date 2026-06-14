"""
TASK-006: Pipeline do Modelo — Treino e Inferência NeKo-PIGNN
=================================================================
Componente 2 do pipeline completo: treinamento e inferência do
modelo híbrido NeKo-PIGNN (Koopman Neural + PI-GNN + Rothermel Loss).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .pipeline_data import PipelineData, N_MUNICIPIOS

logger = logging.getLogger("pipeline_modelo")

CHECKPOINT_DIR = Path("models/checkpoints")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class ResultadoTreino:
    modelo: torch.nn.Module
    historico: dict[str, list[float]]
    metricas: dict
    melhor_epoch: int
    tempo_treino_s: float
    checkpoint_path: Optional[str] = None


class PipelineModelo:
    """Pipeline de treino e inferência para o NeKo-PIGNN."""

    def __init__(
        self,
        node_features: int = 6,
        latent_dim: int = 32,
        gnn_hidden: int = 64,
        koopman_rank: int = 16,
        num_nodes: int = N_MUNICIPIOS,
        beta: float = 0.1,
        alpha: float = 1.0,
        lambda_pde: float = 0.5,
        lambda_gnn: float = 1.0,
        checkpoint_dir: str = "models/checkpoints",
    ):
        self.node_features = node_features
        self.latent_dim = latent_dim
        self.gnn_hidden = gnn_hidden
        self.koopman_rank = koopman_rank
        self.num_nodes = num_nodes
        self.beta = beta
        self.alpha = alpha
        self.lambda_pde = lambda_pde
        self.lambda_gnn = lambda_gnn
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.model: Optional[torch.nn.Module] = None
        self.device = DEVICE
        self.edge_index: Optional[torch.Tensor] = None
        self.edge_attr: Optional[torch.Tensor] = None
        logger.info(f"PipelineModelo: device={self.device}, nos={num_nodes}, latent={latent_dim}")

    def construir_grafo(self, num_nodes: Optional[int] = None, knn: int = 5):
        n = num_nodes or self.num_nodes
        from app.models.inovacao.neko_pignn import build_ceara_graph
        self.edge_index, self.edge_attr = build_ceara_graph(num_nodes=n, knn=knn)
        self.edge_index = self.edge_index.to(self.device)
        self.edge_attr = self.edge_attr.to(self.device)
        logger.info(f"Grafo: {self.edge_index.shape[1]} arestas, {n} nos")
        return self.edge_index, self.edge_attr

    def criar_modelo(self, num_nodes: Optional[int] = None) -> torch.nn.Module:
        from app.models.inovacao.neko_pignn import NeKoPIGNN
        n = num_nodes or self.num_nodes
        self.model = NeKoPIGNN(
            node_features=self.node_features, latent_dim=self.latent_dim,
            gnn_hidden=self.gnn_hidden, num_nodes=n,
            koopman_rank=self.koopman_rank, beta=self.beta,
            alpha=self.alpha, lambda_pde=self.lambda_pde, lambda_gnn=self.lambda_gnn,
        ).to(self.device)
        total_params = sum(p.numel() for p in self.model.parameters())
        logger.info(f"Modelo NeKo-PIGNN criado: {total_params:,} params")
        return self.model

    def treinar(
        self, dados: PipelineData, dados_val: Optional[PipelineData] = None,
        epochs: int = 100, lr: float = 5e-4, weight_decay: float = 1e-5,
        patience: int = 15, min_delta: float = 1e-4, batch_size: int = 32,
        verbose: bool = True,
    ) -> ResultadoTreino:
        if self.model is None:
            self.criar_modelo(num_nodes=dados.X_t.shape[1])
        if self.edge_index is None:
            self.construir_grafo(num_nodes=dados.X_t.shape[1])

        optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=weight_decay)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=patience // 2, min_lr=1e-6
        )

        X_t = dados.X_t.to(self.device)
        X_tp1 = dados.X_tp1.to(self.device)
        val_data = None
        if dados_val is not None:
            val_data = (dados_val.X_t.to(self.device), dados_val.X_tp1.to(self.device))

        wind = torch.rand(X_t.shape[0], X_t.shape[1], 1, device=self.device)
        slope = torch.rand(X_t.shape[0], X_t.shape[1], 1, device=self.device)
        fuel_moist = torch.rand(X_t.shape[0], X_t.shape[1], 1, device=self.device)

        historico = {"train_loss": [], "val_loss": [], "recon_loss": [],
                      "pred_loss": [], "kl_loss": [], "gnn_loss": []}
        best_loss = float("inf")
        best_state = None
        best_epoch = 0
        patience_counter = 0
        t0 = time.time()

        for epoch in range(epochs):
            self.model.train()
            losses_epoch = {k: 0.0 for k in historico if k != "val_loss"}
            n_batches = 0
            indices = torch.randperm(X_t.shape[0])

            for start in range(0, X_t.shape[0], batch_size):
                idx = indices[start:start + batch_size]
                x_batch, y_batch = X_t[idx], X_tp1[idx]
                optimizer.zero_grad()
                outputs = self.model(x_batch, x_tp1=y_batch, edge_index=self.edge_index,
                                      edge_attr=self.edge_attr, wind=wind[idx],
                                      slope=slope[idx], fuel_moisture=fuel_moist[idx])
                outputs["loss"].backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()

                losses_epoch["train_loss"] += outputs["loss"].item()
                losses_epoch["recon_loss"] += outputs.get("recon_loss", torch.tensor(0.0)).item()
                losses_epoch["pred_loss"] += outputs.get("pred_loss", torch.tensor(0.0)).item()
                losses_epoch["kl_loss"] += outputs.get("kl_loss", torch.tensor(0.0)).item()
                losses_epoch["gnn_loss"] += outputs.get("gnn_loss", torch.tensor(0.0)).item()
                n_batches += 1

            for k in losses_epoch:
                losses_epoch[k] = losses_epoch[k] / max(n_batches, 1)
            for k, v in losses_epoch.items():
                historico[k].append(v)

            if val_data is not None:
                self.model.eval()
                val_loss, val_n = 0.0, 0
                with torch.no_grad():
                    for vs in range(0, val_data[0].shape[0], batch_size):
                        ve = min(vs + batch_size, val_data[0].shape[0])
                        vo = self.model(val_data[0][vs:ve], x_tp1=val_data[1][vs:ve],
                                         edge_index=self.edge_index, edge_attr=self.edge_attr)
                        val_loss += vo["loss"].item()
                        val_n += 1
                val_loss /= max(val_n, 1)
                historico["val_loss"].append(val_loss)
                scheduler.step(val_loss)
            else:
                scheduler.step(losses_epoch["train_loss"])

            current_loss = losses_epoch["train_loss"]
            if current_loss < best_loss - min_delta:
                best_loss = current_loss
                best_epoch = epoch
                best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if verbose and ((epoch + 1) % 10 == 0 or epoch == 0):
                log = (f"[{epoch+1:3d}/{epochs}] loss={losses_epoch['train_loss']:.4f} "
                       f"rec={losses_epoch['recon_loss']:.4f} pred={losses_epoch['pred_loss']:.4f} "
                       f"kl={losses_epoch['kl_loss']:.4f} gnn={losses_epoch['gnn_loss']:.4f}")
                if historico["val_loss"]:
                    log += f" val={historico['val_loss'][-1]:.4f}"
                logger.info(log)

            if patience_counter >= patience:
                logger.info(f"Early stopping na epoca {epoch+1} (melhor: {best_epoch+1})")
                break

        t_total = time.time() - t0
        if best_state is not None:
            self.model.load_state_dict(best_state)

        ckpt_path = self._salvar_checkpoint(epochs, best_loss, historico, dados.nomes)
        metricas = self._calcular_metricas(dados)

        logger.info(f"Treino concluido! Melhor loss: {best_loss:.4f} (epoca {best_epoch+1})")
        logger.info(f"Tempo: {t_total:.1f}s")

        return ResultadoTreino(modelo=self.model, historico=historico, metricas=metricas,
                                melhor_epoch=best_epoch, tempo_treino_s=t_total,
                                checkpoint_path=str(ckpt_path))

    @torch.no_grad()
    def prever(self, X_t: torch.Tensor, nomes: Optional[list[str]] = None, passos: int = 1) -> dict:
        if self.model is None:
            raise RuntimeError("Modelo nao treinado.")
        if self.edge_index is None:
            self.construir_grafo(num_nodes=X_t.shape[1])
        self.model.eval()
        X_t = X_t.to(self.device)
        if X_t.dim() == 2:
            X_t = X_t.unsqueeze(0)

        outputs = self.model(X_t, edge_index=self.edge_index, edge_attr=self.edge_attr)
        x_pred = outputs["x_pred"].cpu()
        z_t = outputs.get("z_t", torch.zeros_like(x_pred)).cpu()

        if passos > 1:
            previsoes = [x_pred]
            z_atual = outputs.get("z_tp1", z_t)
            for _ in range(passos - 1):
                z_prox = self.model.koopman.forward_koopman(
                    z_atual.view(-1, self.latent_dim), steps=1
                ).view(z_atual.shape)
                x_prox = self.model.output_decoder(z_prox.view(-1, self.latent_dim))
                x_prox = x_prox.view(x_pred.shape)
                previsoes.append(x_prox.cpu())
                z_atual = z_prox
            x_pred = torch.stack(previsoes, dim=0)

        previsoes_lista = []
        for i in range(X_t.shape[1]):
            mun_nome = nomes[i] if nomes and i < len(nomes) else f"municipio_{i}"
            if passos > 1:
                saida = [x_pred[t, 0, i].tolist() for t in range(passos)]
            else:
                saida = x_pred[0, i].tolist()
            previsoes_lista.append({
                "municipio": mun_nome,
                "features_entrada": X_t[0, i].cpu().tolist(),
                "previsao": saida,
                "estado_latente": z_t[0, i, :8].tolist(),
            })

        return {"modelo": "NeKo-PIGNN", "previsoes": previsoes_lista,
                "num_passos": passos, "num_municipios": X_t.shape[1],
                "dimensao_latente": self.latent_dim,
                "timestamp": datetime.now(timezone.utc).isoformat()}

    def _salvar_checkpoint(self, epochs: int, loss: float, historico: dict, nomes: list[str]) -> Path:
        path = self.checkpoint_dir / "neko_pignn_pipeline.pt"
        torch.save({
            "epoch": epochs, "model_state_dict": self.model.state_dict(), "loss": loss,
            "historico": historico, "nomes_municipios": nomes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {"node_features": self.node_features, "latent_dim": self.latent_dim,
                       "gnn_hidden": self.gnn_hidden, "koopman_rank": self.koopman_rank,
                       "beta": self.beta, "alpha": self.alpha,
                       "lambda_pde": self.lambda_pde, "lambda_gnn": self.lambda_gnn},
        }, path)
        logger.info(f"Checkpoint salvo: {path}")
        return path

    def carregar_checkpoint(self, path: Optional[str] = None) -> bool:
        if path is None:
            path = str(self.checkpoint_dir / "neko_pignn_pipeline.pt")
        if not os.path.exists(path):
            logger.warning(f"Checkpoint nao encontrado: {path}")
            return False
        data = torch.load(path, map_location=self.device, weights_only=False)
        ckpt_keys = set(data["model_state_dict"].keys())
        cfg = data.get("config", {})
        for k in ("node_features", "latent_dim", "gnn_hidden", "koopman_rank", "num_nodes"):
            if k in cfg:
                setattr(self, k, cfg[k])
        self.criar_modelo()
        model_keys = set(self.model.state_dict().keys())

        # Filtra chaves do checkpoint que existem no modelo atual
        compat_keys = {k: v for k, v in data["model_state_dict"].items() if k in model_keys}
        missing = model_keys - ckpt_keys
        extra = ckpt_keys - model_keys
        if compat_keys:
            result = self.model.load_state_dict(compat_keys, strict=False)
            if result.missing_keys:
                logger.warning(f"Chaves nao carregadas (modelo): {result.missing_keys[:5]}...")
            if result.unexpected_keys:
                logger.warning(f"Chaves extras ignoradas (checkpoint): {result.unexpected_keys[:5]}...")
        if missing:
            logger.info(f"Inicializando {len(missing)} chaves novas do modelo")
        if extra:
            logger.info(f"Ignorando {len(extra)} chaves do checkpoint incompatíveis")
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Checkpoint carregado: {path} (loss={data['loss']:.4f}, {len(compat_keys)}/{len(ckpt_keys)} chaves)")
        return True

    def _calcular_metricas(self, dados: PipelineData) -> dict:
        self.model.eval()
        X_t, X_tp1 = dados.X_t.to(self.device), dados.X_tp1.to(self.device)
        with torch.no_grad():
            outputs = self.model(X_t, x_tp1=X_tp1, edge_index=self.edge_index, edge_attr=self.edge_attr)
            pred, target = outputs["x_pred"].cpu().numpy(), X_tp1.cpu().numpy()

        mse = float(np.mean((pred - target) ** 2))
        mae = float(np.mean(np.abs(pred - target)))
        r2 = float(1 - np.sum((pred - target) ** 2) / (np.sum((target - np.mean(target)) ** 2) + 1e-10))
        frp_pred, frp_real = pred[:, :, 1].ravel(), target[:, :, 1].ravel()
        frp_mse = float(np.mean((frp_pred - frp_real) ** 2))
        frp_mae = float(np.mean(np.abs(frp_pred - frp_real)))
        frp_medio_pred = np.mean(pred[:, :, 1], axis=0)
        top3_idx = np.argsort(frp_medio_pred)[-3:][::-1]
        top3 = [(dados.nomes[i], float(frp_medio_pred[i])) for i in top3_idx if i < len(dados.nomes)]
        return {"mse": mse, "mae": mae, "r2": r2, "frp_mse": frp_mse,
                "frp_mae": frp_mae, "top3_frp_previsto": top3,
                "n_amostras": dados.X_t.shape[0], "n_nos": dados.X_t.shape[1]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from pipeline_data import CarregadorDados
    cd = CarregadorDados()
    dados = cd.gerar_dados_sinteticos(num_amostras=80, num_nos=10, ruido=0.03)
    pl = PipelineModelo(node_features=6, latent_dim=16, gnn_hidden=32, koopman_rank=8, num_nodes=10)
    res = pl.treinar(dados, epochs=30, lr=1e-3, batch_size=16)
    print(f"Metricas: mse={res.metricas['mse']:.4f}, mae={res.metricas['mae']:.4f}, r2={res.metricas['r2']:.4f}")
    prev = pl.prever(dados.X_t[:1], nomes=dados.nomes[:10], passos=3)
    print(f"Previsao multi-passo: {prev['num_passos']} passos, {len(prev['previsoes'])} municipios")
    print("pipeline_modelo.py: OK")
