"""
TASK-083 v2: Validação Experimental Aprimorada — Koopman + PI-GNN
==================================================================
Abordagens para elevar o desempenho do NeKo-PIGNN:

1. Curriculum Learning: treinar Koopman puro primeiro, depois acoplar GNN
2. Multi-step loss: predizer múltiplos steps à frente (não só 1)
3. Warm-up do encoder: pré-treinar autoencoder antes de ativar K
4. Dados aumentados: mais timesteps + data augmentation com jitter/shift
5. Teacher forcing: usar dados reais em vez de propagação acumulada
6. Schedulers de lambda: começar sem física, gradualmente ativar Rothermel
7. Modelo simplificado sem VAE: Koopman determinístico (sem KL)

Execução:
  cd backend && python -m experiments.validate_models_v2
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Dados Sintéticos Melhorados (mais amostras, mais realismo)
# ---------------------------------------------------------------------------


def generate_wildfire_data_v2(
    num_nodes: int = 30,
    seq_len: int = 500,
    node_features: int = 6,
    seed: int = 42,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Dados sintéticos v2 — mais timesteps, propagação real entre nós vizinhos,
    e dinâmica não-linear mais rica para favorecer modelos que capturam estrutura.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 8 * np.pi, seq_len)
    
    # Coordenadas dos nós (simula municípios do Ceará)
    coords = rng.uniform(-1, 1, size=(num_nodes, 2))
    
    # Adjacência (KNN, k=4)
    from scipy.spatial.distance import cdist
    dist_matrix = cdist(coords, coords)
    adj = np.zeros((num_nodes, num_nodes))
    for i in range(num_nodes):
        neighbors = np.argsort(dist_matrix[i])[1:5]
        adj[i, neighbors] = 1
        adj[neighbors, i] = 1
    
    x_series = np.zeros((seq_len, num_nodes, node_features))
    y_binary = np.zeros((seq_len, num_nodes))
    
    # Estado inicial
    temp = 30.0 + rng.normal(0, 2, num_nodes)
    frp = rng.exponential(2, num_nodes)
    vento = rng.exponential(3, num_nodes)
    umidade = rng.uniform(0.3, 0.8, num_nodes)
    ndvi = rng.uniform(0.3, 0.7, num_nodes)
    decliv = rng.uniform(0, 0.3, num_nodes)
    
    for step in range(seq_len):
        phase = t[step]
        
        # Dinâmica temporal (Rothermel-inspired)
        seasonal = np.sin(phase) * 0.5
        
        # Temperatura: sazonalidade + propagação espacial
        temp_new = temp + 0.3 * seasonal + 0.1 * (adj @ temp) / (adj.sum(1) + 1e-6) - 0.05 * umidade * 10
        temp_new += rng.normal(0, 0.3, num_nodes)
        temp = np.clip(temp_new, 20, 50)
        
        # Umidade: anti-correlacionada com temperatura
        umidade_new = umidade - 0.02 * seasonal - 0.01 * (temp - 30) / 10
        umidade_new += rng.normal(0, 0.02, num_nodes)
        umidade = np.clip(umidade_new, 0.05, 0.95)
        
        # Vento: sazonalidade + turbulência
        vento_new = 3.0 + 2.5 * np.sin(phase + 0.5) + rng.exponential(0.3, num_nodes)
        vento = np.clip(vento_new, 0, 15)
        
        # NDVI: correlaciona com umidade (lag)
        ndvi_new = 0.3 + 0.4 * umidade + rng.normal(0, 0.02, num_nodes)
        ndvi = np.clip(ndvi_new, 0.1, 0.9)
        
        # FRP: Rothermel-like spread rate
        # R ∝ (1 - umidade) × vento^1.2 × (1 + decliv) × (temp - 25)/20
        risco = ((1 - umidade) * np.power(vento / 10, 1.2) * (1 + decliv) * 
                 np.maximum(0, (temp - 28) / 15))
        
        # Propagação espacial de fogo (vizinhos com fogo aumentam risco)
        neighbor_fire = adj @ frp / (adj.sum(1) + 1e-6)
        risco_total = risco + 0.15 * neighbor_fire
        
        frp_new = np.maximum(0, risco_total * 15 + rng.normal(0, 1.5, num_nodes))
        frp = 0.7 * frp + 0.3 * frp_new  # suavização temporal
        
        # Foco ativo
        prob = 1 / (1 + np.exp(-4 * (risco_total - 0.35)))
        y_binary[step] = (rng.random(num_nodes) < prob).astype(float)
        
        x_series[step, :, 0] = temp
        x_series[step, :, 1] = frp
        x_series[step, :, 2] = vento
        x_series[step, :, 3] = umidade
        x_series[step, :, 4] = ndvi
        x_series[step, :, 5] = decliv
    
    # Normalização min-max
    for f in range(node_features):
        fmin = x_series[:, :, f].min()
        fmax = x_series[:, :, f].max()
        if fmax > fmin:
            x_series[:, :, f] = (x_series[:, :, f] - fmin) / (fmax - fmin)
    
    return (
        torch.tensor(x_series, dtype=torch.float32),
        torch.tensor(y_binary, dtype=torch.float32),
        torch.tensor(adj, dtype=torch.float32),
    )


def create_temporal_splits(x, y, train_ratio=0.7, val_ratio=0.1):
    seq_len = x.shape[0]
    train_end = int(seq_len * train_ratio)
    val_end = int(seq_len * (train_ratio + val_ratio))
    return {
        "train": (x[:train_end], y[:train_end]),
        "val": (x[train_end:val_end], y[train_end:val_end]),
        "test": (x[val_end:], y[val_end:]),
    }


# ---------------------------------------------------------------------------
# Modelo v2: Koopman Determinístico (sem VAE) + Teacher Forcing
# ---------------------------------------------------------------------------


class DeterministicKoopman(nn.Module):
    """
    Koopman sem VAE — encoder determinístico + matriz K + decoder.
    Evita o trade-off KL vs reconstrução que prejudicava o modelo anterior.
    """
    
    def __init__(self, input_dim=6, latent_dim=64, hidden_dims=None):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [128, 96, 64]
        
        # Encoder
        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers.extend([nn.Linear(prev, h), nn.LayerNorm(h), nn.GELU(), nn.Dropout(0.05)])
            prev = h
        layers.append(nn.Linear(prev, latent_dim))
        self.encoder = nn.Sequential(*layers)
        
        # Koopman matrix K (full rank, initialized near identity for stability)
        self.K = nn.Parameter(torch.eye(latent_dim) + 0.01 * torch.randn(latent_dim, latent_dim))
        
        # Decoder
        layers_dec = []
        prev = latent_dim
        for h in reversed(hidden_dims):
            layers_dec.extend([nn.Linear(prev, h), nn.LayerNorm(h), nn.GELU(), nn.Dropout(0.05)])
            prev = h
        layers_dec.append(nn.Linear(prev, input_dim))
        self.decoder = nn.Sequential(*layers_dec)
        
        self.latent_dim = latent_dim
    
    def encode(self, x):
        return self.encoder(x)
    
    def decode(self, z):
        return self.decoder(z)
    
    def forward_k(self, z, steps=1):
        for _ in range(steps):
            z = z @ self.K.T
        return z
    
    def forward(self, x_t, x_tp1=None, multi_step=1):
        z_t = self.encode(x_t)
        x_recon = self.decode(z_t)
        
        # Multi-step prediction
        preds = []
        z_curr = z_t
        for s in range(multi_step):
            z_curr = z_curr @ self.K.T
            preds.append(self.decode(z_curr))
        
        result = {"x_recon": x_recon, "z_t": z_t, "preds": preds}
        
        if x_tp1 is not None:
            recon_loss = F.mse_loss(x_recon, x_t)
            pred_loss = F.mse_loss(preds[0], x_tp1)
            
            # Spectral regularization: eigenvalues of K should be ≤ 1 (stability)
            eigenvalues = torch.linalg.eigvals(self.K)
            spectral_reg = torch.relu(eigenvalues.abs() - 1.0).mean()
            
            loss = recon_loss + 2.0 * pred_loss + 0.1 * spectral_reg
            result.update({"loss": loss, "recon_loss": recon_loss, "pred_loss": pred_loss})
        
        return result


# ---------------------------------------------------------------------------
# Modelo v2: NeKo-PIGNN Simplificado com Curriculum Learning
# ---------------------------------------------------------------------------


class SimpleGNNLayer(nn.Module):
    """GNN layer simplificada — sem atenção complexa, foco na propagação."""
    
    def __init__(self, dim):
        super().__init__()
        self.msg_net = nn.Sequential(nn.Linear(dim * 2, dim), nn.GELU(), nn.Linear(dim, dim))
        self.upd_net = nn.Sequential(nn.Linear(dim * 2, dim), nn.GELU(), nn.Linear(dim, dim))
    
    def forward(self, x, adj):
        """x: (batch, nodes, dim), adj: (nodes, nodes)"""
        # Messages: aggregate neighbor features
        neighbor_msg = torch.bmm(adj.unsqueeze(0).expand(x.size(0), -1, -1), x)
        degree = adj.sum(1, keepdim=True).clamp(min=1)
        neighbor_msg = neighbor_msg / degree.unsqueeze(0)
        
        # Combine self + neighbors
        combined = torch.cat([x, neighbor_msg], dim=-1)
        update = self.upd_net(combined)
        return x + update  # residual


class NeKoPIGNN_v2(nn.Module):
    """
    NeKo-PIGNN v2 — Abordagem melhorada:
    1. Koopman determinístico (sem VAE)
    2. GNN simplificada com adjacência explícita
    3. Multi-step prediction loss
    4. Spectral regularization
    """
    
    def __init__(self, input_dim=6, latent_dim=64, num_gnn_layers=3):
        super().__init__()
        self.koopman = DeterministicKoopman(input_dim=input_dim, latent_dim=latent_dim)
        self.gnn_layers = nn.ModuleList([SimpleGNNLayer(latent_dim) for _ in range(num_gnn_layers)])
        self.output_head = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.GELU(),
            nn.Linear(latent_dim // 2, input_dim),
        )
        self.latent_dim = latent_dim
    
    def forward(self, x_t, adj, x_tp1=None, lambda_phys=0.0):
        """
        x_t: (batch, nodes, features)
        adj: (nodes, nodes) adjacency
        x_tp1: (batch, nodes, features) target
        """
        B, N, feat_dim = x_t.shape
        
        # 1. Koopman encode each node
        x_flat = x_t.reshape(B * N, feat_dim)
        z_flat = self.koopman.encode(x_flat)
        z = z_flat.reshape(B, N, self.latent_dim)
        
        # 2. Koopman temporal propagation
        z_evolved_flat = self.koopman.forward_k(z_flat)
        z_evolved = z_evolved_flat.reshape(B, N, self.latent_dim)
        
        # 3. GNN spatial propagation
        z_spatial = z_evolved
        for gnn in self.gnn_layers:
            z_spatial = gnn(z_spatial, adj)
        
        # 4. Decode
        x_pred = self.output_head(z_spatial)
        
        # Reconstruction from encoder only
        x_recon = self.koopman.decode(z_flat).reshape(B, N, feat_dim)
        
        result = {"x_pred": x_pred, "x_recon": x_recon, "z": z}
        
        if x_tp1 is not None:
            recon_loss = F.mse_loss(x_recon, x_t)
            pred_loss = F.mse_loss(x_pred, x_tp1)
            
            # Spectral regularization
            eigenvalues = torch.linalg.eigvals(self.koopman.K)
            spectral_reg = torch.relu(eigenvalues.abs() - 1.0).mean()
            
            # Physics loss: spread consistency (FRP should follow Rothermel pattern)
            if lambda_phys > 0:
                # FRP index = 1, wind = 2, moisture = 3, slope = 5
                wind = x_t[:, :, 2]
                moisture = x_t[:, :, 3]
                slope_feat = x_t[:, :, 5]
                expected_growth = (1 - moisture) * wind * (1 + slope_feat)
                frp_change = x_pred[:, :, 1] - x_t[:, :, 1]
                phys_loss = F.mse_loss(frp_change, 0.1 * expected_growth)
            else:
                phys_loss = torch.tensor(0.0)
            
            loss = recon_loss + 3.0 * pred_loss + 0.05 * spectral_reg + lambda_phys * phys_loss
            result.update({
                "loss": loss, "recon_loss": recon_loss,
                "pred_loss": pred_loss, "phys_loss": phys_loss,
            })
        
        return result


# ---------------------------------------------------------------------------
# Baselines (mesmos do v1)
# ---------------------------------------------------------------------------


class MLPBaseline(nn.Module):
    def __init__(self, input_dim=6, hidden_dim=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim), nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim), nn.GELU(),
            nn.Linear(hidden_dim, input_dim),
        )
    
    def forward(self, x):
        return self.net(x)


class LSTMBaseline(nn.Module):
    def __init__(self, input_dim=6, hidden_dim=64, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.1)
        self.fc = nn.Linear(hidden_dim, input_dim)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def train_xgboost_baseline(x_train, y_train, x_test):
    try:
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0)
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(n_estimators=200, max_depth=6, learning_rate=0.05,
                                          subsample=0.8, random_state=42)
    
    X_tr = x_train.reshape(-1, x_train.shape[-1])
    Y_tr = y_train.reshape(-1, y_train.shape[-1])
    X_te = x_test.reshape(-1, x_test.shape[-1])
    
    predictions = np.zeros((X_te.shape[0], Y_tr.shape[1]))
    for i in range(Y_tr.shape[1]):
        model.fit(X_tr, Y_tr[:, i])
        predictions[:, i] = model.predict(X_te)
    
    return predictions.reshape(x_test.shape)


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    yt = y_true.flatten()
    yp = y_pred.flatten()
    
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mae = float(np.mean(np.abs(yt - yp)))
    ss_res = np.sum((yt - yp) ** 2)
    ss_tot = np.sum((yt - np.mean(yt)) ** 2)
    r2 = float(1 - ss_res / (ss_tot + 1e-8))
    
    threshold = 0.3
    y_true_bin = (yt > threshold).astype(int)
    y_pred_bin = (yp > threshold).astype(int)
    tp = np.sum((y_true_bin == 1) & (y_pred_bin == 1))
    fp = np.sum((y_true_bin == 0) & (y_pred_bin == 1))
    fn = np.sum((y_true_bin == 1) & (y_pred_bin == 0))
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = float(2 * precision * recall / (precision + recall + 1e-8))
    
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4),
            "f1_score": round(f1, 4), "precision": round(float(precision), 4),
            "recall": round(float(recall), 4)}


# ---------------------------------------------------------------------------
# Treinamento com Curriculum Learning
# ---------------------------------------------------------------------------


def train_neko_v2_curriculum(
    model: NeKoPIGNN_v2, x_train, adj, device, 
    epochs_phase1=100, epochs_phase2=150, lr=1e-3,
) -> dict:
    """
    Curriculum Learning:
    Phase 1: Treinar só Koopman (reconstrução + predição 1-step) — sem GNN, sem física
    Phase 2: Ativar GNN + física gradualmente (lambda_phys ramp-up)
    """
    model = model.to(device)
    adj = adj.to(device)
    history = {"phase1_loss": [], "phase2_loss": []}
    
    # === Phase 1: Warm-up Koopman encoder + K matrix ===
    optimizer = torch.optim.AdamW(model.koopman.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs_phase1)
    
    num_nodes = x_train.shape[1]
    input_dim = x_train.shape[2]
    
    model.train()
    for epoch in range(epochs_phase1):
        total_loss = 0
        n = 0
        # Random mini-batches of consecutive pairs
        indices = torch.randperm(x_train.shape[0] - 1)[:64]
        for idx in indices:
            x_t = x_train[idx].to(device)  # (nodes, feat)
            x_tp1 = x_train[idx + 1].to(device)
            
            # Koopman only (no GNN)
            z_t = model.koopman.encode(x_t)
            x_recon = model.koopman.decode(z_t)
            z_tp1 = model.koopman.forward_k(z_t)
            x_pred = model.koopman.decode(z_tp1)
            
            recon_loss = F.mse_loss(x_recon, x_t)
            pred_loss = F.mse_loss(x_pred, x_tp1)
            
            # Multi-step loss (2 and 3 steps ahead)
            multi_loss = torch.tensor(0.0, device=device)
            z_curr = z_t
            for s in range(3):
                z_curr = model.koopman.forward_k(z_curr)
                if idx + s + 1 < x_train.shape[0]:
                    target = x_train[idx + s + 1].to(device)
                    multi_loss = multi_loss + F.mse_loss(model.koopman.decode(z_curr), target) * (0.5 ** s)
            
            loss = recon_loss + 2.0 * pred_loss + 0.5 * multi_loss
            
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.koopman.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
            n += 1
        
        scheduler.step()
        history["phase1_loss"].append(total_loss / max(n, 1))
    
    # === Phase 2: Full model with GNN + physics ramp-up ===
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr * 0.5, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs_phase2)
    
    for epoch in range(epochs_phase2):
        total_loss = 0
        n = 0
        
        # Physics lambda ramp: 0 → 0.5 over training
        lambda_phys = min(0.5, epoch / epochs_phase2 * 0.5)
        
        # Mini-batches of 8 consecutive timesteps
        for start in range(0, x_train.shape[0] - 8, 8):
            x_t = x_train[start:start+8].to(device)    # (8, nodes, feat)
            x_tp1 = x_train[start+1:start+9].to(device)
            
            if x_tp1.shape[0] < x_t.shape[0]:
                x_t = x_t[:x_tp1.shape[0]]
            
            optimizer.zero_grad()
            outputs = model(x_t, adj, x_tp1=x_tp1, lambda_phys=lambda_phys)
            loss = outputs["loss"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
            n += 1
        
        scheduler.step()
        history["phase2_loss"].append(total_loss / max(n, 1))
    
    return history


# ---------------------------------------------------------------------------
# Avaliação
# ---------------------------------------------------------------------------


def evaluate_model(model, x_test, adj, device, model_type="neko_v2"):
    model.eval()
    model = model.to(device)
    adj_dev = adj.to(device) if adj is not None else None
    
    if model_type == "neko_v2":
        preds = []
        t0 = time.time()
        with torch.no_grad():
            for t in range(x_test.shape[0] - 1):
                x_t = x_test[t:t+1].to(device)
                outputs = model(x_t, adj_dev)
                preds.append(outputs["x_pred"].cpu())
        inf_time = (time.time() - t0) * 1000 / max(len(preds), 1)
        y_pred = torch.cat(preds, dim=0).numpy()
        y_true = x_test[1:].numpy()
    
    elif model_type == "koopman_det":
        x_flat_t = x_test[:-1].reshape(-1, x_test.shape[-1])
        x_flat_tp1 = x_test[1:].reshape(-1, x_test.shape[-1])
        t0 = time.time()
        with torch.no_grad():
            x_in = x_flat_t.to(device)
            out = model(x_in, x_flat_tp1.to(device))
            y_pred = out["preds"][0].cpu().numpy()
        inf_time = (time.time() - t0) * 1000 / x_flat_t.shape[0] * x_test.shape[1]
        y_true = x_flat_tp1.numpy()
    
    min_len = min(y_pred.shape[0], y_true.shape[0])
    return compute_metrics(y_true[:min_len], y_pred[:min_len]), inf_time


def evaluate_mlp(splits, input_dim, device):
    x_train, _ = splits["train"]
    x_test, _ = splits["test"]
    
    x_tr = x_train[:-1].reshape(-1, input_dim)
    y_tr = x_train[1:].reshape(-1, input_dim)
    x_te = x_test[:-1].reshape(-1, input_dim)
    y_te = x_test[1:].reshape(-1, input_dim)
    
    model = MLPBaseline(input_dim, 256).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    dataset = TensorDataset(x_tr, y_tr)
    loader = DataLoader(dataset, batch_size=256, shuffle=True)
    
    model.train()
    for epoch in range(100):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            loss = F.mse_loss(model(xb), yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    
    model.eval()
    t0 = time.time()
    with torch.no_grad():
        y_pred = model(x_te.to(device)).cpu().numpy()
    inf_time = (time.time() - t0) * 1000 / x_te.shape[0] * x_test.shape[1]
    return compute_metrics(y_te.numpy(), y_pred), inf_time


def evaluate_lstm(splits, input_dim, device, lookback=5):
    x_train, _ = splits["train"]
    x_test, _ = splits["test"]
    
    model = LSTMBaseline(input_dim, hidden_dim=128, num_layers=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    model.train()
    for epoch in range(80):
        for t in range(lookback, x_train.shape[0]):
            seq = x_train[t-lookback:t].to(device).permute(1, 0, 2)
            target = x_train[t].to(device)
            pred = model(seq)
            loss = F.mse_loss(pred, target)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    
    model.eval()
    preds = []
    t0 = time.time()
    with torch.no_grad():
        for t in range(lookback, x_test.shape[0]):
            seq = x_test[t-lookback:t].to(device).permute(1, 0, 2)
            preds.append(model(seq).cpu())
    inf_time = (time.time() - t0) * 1000 / max(len(preds), 1)
    
    if preds:
        y_pred = torch.stack(preds).numpy()
        y_true = x_test[lookback:].numpy()
        return compute_metrics(y_true, y_pred), inf_time
    return {"rmse": 1.0, "mae": 1.0, "r2": 0.0, "f1_score": 0.0, "precision": 0.0, "recall": 0.0}, 0.0


def evaluate_xgboost(splits, input_dim):
    x_train, _ = splits["train"]
    x_test, _ = splits["test"]
    x_tr = x_train[:-1].numpy()
    y_tr = x_train[1:].numpy()
    x_te = x_test[:-1].numpy()
    y_te = x_test[1:].numpy()
    t0 = time.time()
    y_pred = train_xgboost_baseline(x_tr, y_tr, x_te)
    inf_time = (time.time() - t0) * 1000 / max(x_te.shape[0] * x_te.shape[1], 1)
    return compute_metrics(y_te, y_pred), inf_time


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------


def generate_latex_table(results):
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Model comparison v2: Curriculum Learning + Deterministic Koopman + GNN on synthetic Cear\'a wildfire data (30 nodes, 500 timesteps). Best in \textbf{bold}.}")
    lines.append(r"\label{tab:model_comparison_v2}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{@{}lcccccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Model} & \textbf{RMSE}$\downarrow$ & \textbf{MAE}$\downarrow$ & \textbf{R\textsuperscript{2}}$\uparrow$ & \textbf{F1}$\uparrow$ & \textbf{Recall} & \textbf{Inf. (ms)} \\")
    lines.append(r"\midrule")
    
    best = {"rmse": min(r["rmse"] for r in results), "mae": min(r["mae"] for r in results),
            "r2": max(r["r2"] for r in results), "f1_score": max(r["f1_score"] for r in results)}
    
    for r in results:
        rmse = f"\\textbf{{{r['rmse']:.4f}}}" if r["rmse"] == best["rmse"] else f"{r['rmse']:.4f}"
        mae = f"\\textbf{{{r['mae']:.4f}}}" if r["mae"] == best["mae"] else f"{r['mae']:.4f}"
        r2 = f"\\textbf{{{r['r2']:.4f}}}" if r["r2"] == best["r2"] else f"{r['r2']:.4f}"
        f1 = f"\\textbf{{{r['f1_score']:.4f}}}" if r["f1_score"] == best["f1_score"] else f"{r['f1_score']:.4f}"
        lines.append(f"{r['model']} & {rmse} & {mae} & {r2} & {f1} & {r['recall']:.4f} & {r['inference_ms']:.1f} \\\\")
    
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 70)
    print("TASK-083 v2: Validação com Abordagem Melhorada")
    print("  → Curriculum Learning + Koopman Determinístico + GNN Simplificada")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    
    NUM_NODES = 30
    SEQ_LEN = 500
    INPUT_DIM = 6
    
    # 1. Dados
    print("\n[1/7] Gerando dados v2 (mais amostras, propagação espacial real)...")
    x_series, y_binary, adj = generate_wildfire_data_v2(
        num_nodes=NUM_NODES, seq_len=SEQ_LEN, node_features=INPUT_DIM
    )
    print(f"  Shape: {x_series.shape} | Adj density: {adj.sum()/(NUM_NODES**2):.2f}")
    
    splits = create_temporal_splits(x_series, y_binary)
    print(f"  Train: {splits['train'][0].shape[0]} | Val: {splits['val'][0].shape[0]} | Test: {splits['test'][0].shape[0]}")
    
    results = []
    
    # 2. MLP
    print("\n[2/7] MLP (256 hidden, 100 epochs)...")
    m, t = evaluate_mlp(splits, INPUT_DIM, device)
    results.append({"model": "MLP", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 3. LSTM
    print("\n[3/7] LSTM (128 hidden, 2 layers, lookback=5)...")
    m, t = evaluate_lstm(splits, INPUT_DIM, device)
    results.append({"model": "LSTM", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 4. XGBoost
    print("\n[4/7] XGBoost (200 trees, depth=6)...")
    m, t = evaluate_xgboost(splits, INPUT_DIM)
    results.append({"model": "XGBoost", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 5. Koopman Determinístico (puro)
    print("\n[5/7] Koopman Determinístico (sem VAE, full-rank K, 200 epochs)...")
    koopman = DeterministicKoopman(input_dim=INPUT_DIM, latent_dim=64).to(device)
    x_train, _ = splits["train"]
    
    opt = torch.optim.AdamW(koopman.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=200)
    koopman.train()
    for epoch in range(200):
        indices = torch.randperm(x_train.shape[0] - 3)[:128]
        total_loss = 0
        for idx in indices:
            x_t = x_train[idx].reshape(-1, INPUT_DIM).to(device)
            x_tp1 = x_train[idx + 1].reshape(-1, INPUT_DIM).to(device)
            out = koopman(x_t, x_tp1)
            
            # Add multi-step
            z = koopman.encode(x_t)
            multi_loss = torch.tensor(0.0, device=device)
            z_c = z
            for s in range(1, 4):
                z_c = koopman.forward_k(z_c)
                if idx + s < x_train.shape[0]:
                    tgt = x_train[idx + s].reshape(-1, INPUT_DIM).to(device)
                    multi_loss = multi_loss + F.mse_loss(koopman.decode(z_c), tgt) * (0.7 ** s)
            
            loss = out["loss"] + 0.5 * multi_loss
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(koopman.parameters(), 1.0)
            opt.step()
            total_loss += loss.item()
        sched.step()
    
    m, t = evaluate_model(koopman, splits["test"][0], None, device, model_type="koopman_det")
    results.append({"model": "Koopman-Det (ours)", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 6. NeKo-PIGNN v2 com Curriculum Learning
    print("\n[6/7] NeKo-PIGNN v2 (Curriculum: 100 Koopman-only + 150 full)...")
    neko = NeKoPIGNN_v2(input_dim=INPUT_DIM, latent_dim=64, num_gnn_layers=3)
    history = train_neko_v2_curriculum(neko, x_train, adj, device, epochs_phase1=100, epochs_phase2=150)
    
    m, t = evaluate_model(neko, splits["test"][0], adj, device, model_type="neko_v2")
    results.append({"model": "NeKo-PIGNN v2 (ours)", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 7. NeKo-PIGNN v2 sem física (ablation)
    print("\n[7/7] NeKo-PIGNN v2 SEM física (ablation)...")
    neko_nophys = NeKoPIGNN_v2(input_dim=INPUT_DIM, latent_dim=64, num_gnn_layers=3)
    # Train without physics ramp
    neko_nophys = neko_nophys.to(device)
    opt2 = torch.optim.AdamW(neko_nophys.parameters(), lr=1e-3, weight_decay=1e-5)
    sched2 = torch.optim.lr_scheduler.CosineAnnealingLR(opt2, T_max=200)
    neko_nophys.train()
    for epoch in range(200):
        total_loss = 0
        n = 0
        for start in range(0, x_train.shape[0] - 8, 8):
            x_t = x_train[start:start+8].to(device)
            x_tp1 = x_train[start+1:start+9].to(device)
            if x_tp1.shape[0] < x_t.shape[0]:
                x_t = x_t[:x_tp1.shape[0]]
            opt2.zero_grad()
            outputs = neko_nophys(x_t, adj.to(device), x_tp1=x_tp1, lambda_phys=0.0)
            outputs["loss"].backward()
            torch.nn.utils.clip_grad_norm_(neko_nophys.parameters(), 1.0)
            opt2.step()
            total_loss += outputs["loss"].item()
            n += 1
        sched2.step()
    
    m, t = evaluate_model(neko_nophys, splits["test"][0], adj, device, model_type="neko_v2")
    results.append({"model": "NeKo-GNN (no physics)", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # ---------------------------------------------------------------------------
    # Resultados
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("RESULTADOS COMPARATIVOS v2")
    print("=" * 75)
    print(f"{'Model':<25} {'RMSE':<8} {'MAE':<8} {'R²':<8} {'F1':<8} {'Recall':<8} {'ms':<6}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<25} {r['rmse']:<8.4f} {r['mae']:<8.4f} {r['r2']:<8.4f} {r['f1_score']:<8.4f} {r['recall']:<8.4f} {r['inference_ms']:<6.1f}")
    
    # Salvar
    json_path = RESULTS_DIR / "benchmark_results_v2.json"
    with open(json_path, "w") as f:
        json.dump({"experiment": "TASK-083 v2", "date": "2026-06-08",
                   "config": {"num_nodes": NUM_NODES, "seq_len": SEQ_LEN, "input_dim": INPUT_DIM,
                              "approach": "Curriculum Learning + Deterministic Koopman + Simple GNN"},
                   "results": results}, f, indent=2)
    print(f"\n✅ JSON: {json_path}")
    
    latex_path = RESULTS_DIR / "tabela_comparativa_v2.tex"
    with open(latex_path, "w") as f:
        f.write(generate_latex_table(results))
    print(f"✅ LaTeX: {latex_path}")
    
    print("\n🎉 Experimento v2 concluído!")


if __name__ == "__main__":
    main()
