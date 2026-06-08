"""
TASK-083 v4: NeKo-PIGNN Otimizado para Dados Reais
====================================================
Diagnóstico v3: NeKo-PIGNN (R²=0.756) perde para MLP (R²=0.799).

Soluções implementadas:
1. Feature Engineering: lag features (t-1, t-2, t-3), rolling mean/std
2. Residual Learning: modelo prediz Δx = x_{t+1} - x_t (não x_{t+1} direto)
3. Modelo Leve: menos parâmetros para evitar overfitting com 67 amostras
4. Ensemble: combina Koopman + GNN + Heurística climática com pesos aprendidos
5. Temporal Augmentation: jitter + shift nos dados de treino
6. Adjacência ponderada por correlação real de focos (não apenas geográfica)

Execução:
  cd backend && python -m experiments.validate_real_v4
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

RESULTS_DIR = Path(__file__).parent / "results"
DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# 1. Feature Engineering
# ---------------------------------------------------------------------------

def engineer_features(x_raw: np.ndarray, lookback: int = 3) -> np.ndarray:
    """
    Adiciona lag features e rolling stats ao dataset.
    x_raw: (days, municipalities, features)
    Returns: (days - lookback, municipalities, features * (1 + lookback + 2))
    """
    days, mun, feat = x_raw.shape
    
    # Features originais + lags + rolling mean + rolling std
    # Total features: feat * (1 + lookback) + feat * 2 = feat * (lookback + 3)
    new_feat = feat * (lookback + 3)
    x_out = np.zeros((days - lookback, mun, new_feat))
    
    for d in range(lookback, days):
        idx = d - lookback
        # Features atuais
        x_out[idx, :, :feat] = x_raw[d]
        
        # Lag features (t-1, t-2, t-3)
        for lag in range(1, lookback + 1):
            start = feat * lag
            end = feat * (lag + 1)
            x_out[idx, :, start:end] = x_raw[d - lag]
        
        # Rolling mean (últimos lookback+1 dias)
        window = x_raw[d - lookback:d + 1]
        start = feat * (lookback + 1)
        x_out[idx, :, start:start + feat] = window.mean(axis=0)
        
        # Rolling std
        start2 = start + feat
        x_out[idx, :, start2:start2 + feat] = window.std(axis=0)
    
    return x_out


# ---------------------------------------------------------------------------
# 2. Modelos Melhorados
# ---------------------------------------------------------------------------

class ResidualKoopman(nn.Module):
    """
    Koopman que prediz o RESIDUAL Δx = x_{t+1} - x_t.
    Skip connection: x_pred = x_t + model(x_t)
    Muito mais fácil de aprender (alvo centrado em zero).
    """
    def __init__(self, input_dim, latent_dim=32):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, latent_dim), nn.GELU(),
            nn.Linear(latent_dim, latent_dim), nn.GELU(),
        )
        self.K = nn.Parameter(torch.eye(latent_dim) * 0.99 + 0.01 * torch.randn(latent_dim, latent_dim))
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, latent_dim), nn.GELU(),
            nn.Linear(latent_dim, input_dim),
        )
        self.input_dim = input_dim
    
    def forward(self, x_t, return_residual=False):
        z = self.encoder(x_t)
        z_next = z @ self.K.T
        delta = self.decoder(z_next)  # prediz Δx
        x_pred = x_t[:, :self.input_dim] + delta  # skip connection (usa apenas feat originais se augmented)
        if return_residual:
            return x_pred, delta
        return x_pred


class ResidualGNN(nn.Module):
    """GNN residual leve que propaga informação entre vizinhos."""
    def __init__(self, dim, num_layers=2):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.Sequential(nn.Linear(dim * 2, dim), nn.GELU())
            for _ in range(num_layers)
        ])
    
    def forward(self, x, adj):
        """x: (batch, nodes, dim), adj: (nodes, nodes)"""
        for layer in self.layers:
            deg = adj.sum(1, keepdim=True).clamp(min=1)
            neigh = torch.bmm(adj.unsqueeze(0).expand(x.size(0), -1, -1), x) / deg.unsqueeze(0)
            x = x + layer(torch.cat([x, neigh], dim=-1))
        return x


class NeKoPIGNN_v4(nn.Module):
    """
    NeKo-PIGNN v4 — Otimizado para dados reais escassos:
    - Residual learning (prediz Δx)
    - Modelo leve (menos parâmetros)  
    - GNN residual
    - Ensemble head com pesos aprendidos
    """
    def __init__(self, input_dim, output_dim, latent_dim=32, num_gnn_layers=2):
        super().__init__()
        self.koopman = ResidualKoopman(input_dim, latent_dim)
        self.gnn = ResidualGNN(latent_dim, num_gnn_layers)
        
        # Projection to latent for GNN
        self.proj_in = nn.Linear(input_dim, latent_dim)
        self.proj_out = nn.Linear(latent_dim, output_dim)
        
        # Ensemble: combina Koopman + GNN + input direto
        self.ensemble = nn.Sequential(
            nn.Linear(output_dim * 3, output_dim * 2), nn.GELU(),
            nn.Linear(output_dim * 2, output_dim),
        )
        
        self.output_dim = output_dim
        self.input_dim = input_dim
    
    def forward(self, x_t, adj):
        B, N, F = x_t.shape
        
        # Branch 1: Koopman residual
        x_flat = x_t.reshape(B * N, F)
        koopman_pred = self.koopman(x_flat).reshape(B, N, self.input_dim)
        koopman_out = koopman_pred[:, :, :self.output_dim]
        
        # Branch 2: GNN propagation
        z = self.proj_in(x_t)
        z_gnn = self.gnn(z, adj)
        gnn_out = self.proj_out(z_gnn)
        
        # Branch 3: Persistence (prediz que amanhã = hoje)
        persist_out = x_t[:, :, :self.output_dim]
        
        # Ensemble: aprende pesos ótimos
        combined = torch.cat([koopman_out, gnn_out, persist_out], dim=-1)
        return self.ensemble(combined)


# ---------------------------------------------------------------------------
# 3. Baselines
# ---------------------------------------------------------------------------

class MLPResidual(nn.Module):
    """MLP com skip connection (residual)."""
    def __init__(self, input_dim, output_dim, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(0.05),
            nn.Linear(hidden, output_dim),
        )
        self.skip = nn.Linear(input_dim, output_dim) if input_dim != output_dim else nn.Identity()
    
    def forward(self, x):
        return self.net(x) + self.skip(x)


class LSTMModel(nn.Module):
    def __init__(self, input_dim, output_dim, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, 2, batch_first=True, dropout=0.1)
        self.fc = nn.Linear(hidden, output_dim)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


# ---------------------------------------------------------------------------
# 4. Dados
# ---------------------------------------------------------------------------

def load_and_prepare():
    """Carrega dados reais e aplica feature engineering."""
    with open(DATA_DIR / "climate_ceara_90d.json") as f:
        climate = json.load(f)
    with open(DATA_DIR / "firms_ceara_7d.json") as f:
        firms = json.load(f)
    with open(DATA_DIR / "inpe_ceara_historico.json") as f:
        inpe = json.load(f)
    
    municipios = list(climate.keys())
    num_mun = len(municipios)
    dates = climate[municipios[0]]["dates"]
    num_days = len(dates)
    
    coords = np.array([[climate[m]["lat"], climate[m]["lon"]] for m in municipios])
    
    # Focos por município/dia
    focos_map = defaultdict(lambda: defaultdict(int))
    from scipy.spatial.distance import cdist
    
    def closest_mun_idx(lat, lon):
        dists = np.sqrt((coords[:, 0] - lat)**2 + (coords[:, 1] - lon)**2)
        return int(np.argmin(dists))
    
    for f in firms:
        try:
            idx = closest_mun_idx(float(f["latitude"]), float(f["longitude"]))
            focos_map[idx][f.get("acq_date", "")] += 1
        except: pass
    
    for f in inpe:
        try:
            idx = closest_mun_idx(float(f["lat"]), float(f["lon"]))
            dt = f.get("date", "") or (f.get("data_hora_gmt", "")[:10])
            focos_map[idx][dt] += 1
        except: pass
    
    # Dataset: (days, municipalities, 6)
    x_raw = np.zeros((num_days, num_mun, 6))
    for i, mun in enumerate(municipios):
        c = climate[mun]
        for d in range(num_days):
            x_raw[d, i, 0] = (c["temp_max"][d] or 30) 
            x_raw[d, i, 1] = (c["temp_min"][d] or 22)
            x_raw[d, i, 2] = (c["humidity"][d] or 60)
            x_raw[d, i, 3] = (c["wind_max"][d] or 5)
            x_raw[d, i, 4] = (c["precip"][d] or 0)
            x_raw[d, i, 5] = focos_map[i].get(dates[d], 0)
    
    # Normalização
    stats = {}
    for f in range(6):
        fmin, fmax = x_raw[:,:,f].min(), x_raw[:,:,f].max()
        stats[f] = (fmin, fmax)
        if fmax > fmin:
            x_raw[:,:,f] = (x_raw[:,:,f] - fmin) / (fmax - fmin)
    
    # Adjacência ponderada por correlação de focos
    focos_series = x_raw[:, :, 5]  # (days, mun)
    corr = np.corrcoef(focos_series.T)
    corr = np.nan_to_num(corr, 0)
    # KNN + correlação
    dist_matrix = cdist(coords, coords)
    adj = np.zeros((num_mun, num_mun))
    for i in range(num_mun):
        neighbors = np.argsort(dist_matrix[i])[1:6]
        for n in neighbors:
            weight = max(0, corr[i, n]) + 0.5 / (dist_matrix[i, n] + 0.01)
            adj[i, n] = weight
            adj[n, i] = weight
    # Normalizar
    row_sum = adj.sum(axis=1, keepdims=True)
    adj = adj / (row_sum + 1e-8)
    
    print(f"  Raw: {x_raw.shape} | Adj density: {(adj > 0).sum() / adj.size:.2f}")
    
    # Feature engineering
    lookback = 3
    x_eng = engineer_features(x_raw, lookback=lookback)
    print(f"  Engineered: {x_eng.shape} ({x_eng.shape[-1]} features)")
    
    return x_raw, x_eng, adj, lookback, stats


def temporal_split(x, train_ratio=0.7, val_ratio=0.1):
    n = x.shape[0]
    tr = int(n * train_ratio)
    va = int(n * (train_ratio + val_ratio))
    return x[:tr], x[tr:va], x[va:]


# ---------------------------------------------------------------------------
# 5. Métricas
# ---------------------------------------------------------------------------

def compute_metrics(y_true, y_pred):
    yt, yp = y_true.flatten(), y_pred.flatten()
    rmse = float(np.sqrt(np.mean((yt - yp)**2)))
    mae = float(np.mean(np.abs(yt - yp)))
    ss_res = np.sum((yt - yp)**2)
    ss_tot = np.sum((yt - np.mean(yt))**2)
    r2 = float(1 - ss_res / (ss_tot + 1e-8))
    
    thr = 0.3
    tp = np.sum((yt > thr) & (yp > thr))
    fp = np.sum((yt <= thr) & (yp > thr))
    fn = np.sum((yt > thr) & (yp <= thr))
    prec = tp / (tp + fp + 1e-8)
    rec = tp / (tp + fn + 1e-8)
    f1 = float(2 * prec * rec / (prec + rec + 1e-8))
    
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4),
            "f1_score": round(f1, 4), "precision": round(float(prec), 4), "recall": round(float(rec), 4)}


# ---------------------------------------------------------------------------
# 6. Training & Evaluation
# ---------------------------------------------------------------------------

def train_eval_mlp_residual(x_train_eng, x_test_eng, x_train_raw, x_test_raw, output_dim, device):
    """MLP com feature engineering + residual."""
    input_dim = x_train_eng.shape[-1]
    
    x_tr = x_train_eng[:-1].reshape(-1, input_dim)
    y_tr = x_train_raw[1:, :, :output_dim].reshape(-1, output_dim)  # target = raw features next day
    x_te = x_test_eng[:-1].reshape(-1, input_dim)
    y_te = x_test_raw[1:, :, :output_dim].reshape(-1, output_dim)
    
    model = MLPResidual(input_dim, output_dim, hidden=128).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, 150)
    
    x_tr_t = torch.tensor(x_tr, dtype=torch.float32)
    y_tr_t = torch.tensor(y_tr, dtype=torch.float32)
    loader = DataLoader(TensorDataset(x_tr_t, y_tr_t), batch_size=64, shuffle=True)
    
    model.train()
    for ep in range(150):
        for xb, yb in loader:
            loss = F.mse_loss(model(xb.to(device)), yb.to(device))
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()
    
    model.eval()
    t0 = time.time()
    with torch.no_grad():
        pred = model(torch.tensor(x_te, dtype=torch.float32).to(device)).cpu().numpy()
    t_ms = (time.time() - t0) * 1000 / max(len(x_te), 1)
    return compute_metrics(y_te, pred), t_ms


def train_eval_xgboost(x_train_eng, x_test_eng, x_train_raw, x_test_raw, output_dim):
    """XGBoost com features engineered."""
    x_tr = x_train_eng[:-1].reshape(-1, x_train_eng.shape[-1])
    y_tr = x_train_raw[1:, :, :output_dim].reshape(-1, output_dim)
    x_te = x_test_eng[:-1].reshape(-1, x_test_eng.shape[-1])
    y_te = x_test_raw[1:, :, :output_dim].reshape(-1, output_dim)
    
    try:
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0)
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.05,
                                          subsample=0.8, random_state=42)
    
    t0 = time.time()
    preds = np.zeros_like(y_te)
    for i in range(output_dim):
        model.fit(x_tr, y_tr[:, i])
        preds[:, i] = model.predict(x_te)
    t_ms = (time.time() - t0) * 1000 / max(len(x_te), 1)
    return compute_metrics(y_te, preds), t_ms


def train_eval_neko_v4(x_train_eng, x_test_eng, x_train_raw, x_test_raw, adj_np, output_dim, device):
    """NeKo-PIGNN v4 com todas as melhorias."""
    input_dim = x_train_eng.shape[-1]
    num_mun = x_train_eng.shape[1]
    adj = torch.tensor(adj_np, dtype=torch.float32).to(device)
    
    model = NeKoPIGNN_v4(input_dim, output_dim, latent_dim=32, num_gnn_layers=2).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, 200)
    
    # Targets: raw features do dia seguinte (apenas output_dim features)
    x_tr_t = torch.tensor(x_train_eng[:-1], dtype=torch.float32)
    y_tr_t = torch.tensor(x_train_raw[1:, :, :output_dim], dtype=torch.float32)
    
    # Data augmentation: jitter
    model.train()
    for ep in range(200):
        # Shuffle temporal
        indices = torch.randperm(x_tr_t.shape[0])
        for start in range(0, len(indices), 8):
            batch_idx = indices[start:start+8]
            x_b = x_tr_t[batch_idx].to(device)
            y_b = y_tr_t[batch_idx].to(device)
            
            # Jitter augmentation
            if ep < 150:
                x_b = x_b + 0.01 * torch.randn_like(x_b)
            
            pred = model(x_b, adj)
            loss = F.mse_loss(pred, y_b)
            
            # Spectral regularization on Koopman K
            eigs = torch.linalg.eigvals(model.koopman.K)
            spec_reg = torch.relu(eigs.abs() - 1.0).mean()
            loss = loss + 0.01 * spec_reg
            
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()
    
    # Eval
    model.eval()
    x_te_t = torch.tensor(x_test_eng[:-1], dtype=torch.float32)
    y_te = x_test_raw[1:, :, :output_dim]
    
    t0 = time.time()
    with torch.no_grad():
        pred = model(x_te_t.to(device), adj).cpu().numpy()
    t_ms = (time.time() - t0) * 1000 / max(x_te_t.shape[0], 1)
    
    return compute_metrics(y_te, pred), t_ms


def train_eval_lstm(x_train_eng, x_test_eng, x_train_raw, x_test_raw, output_dim, device, lookback=5):
    """LSTM com features engineered."""
    input_dim = x_train_eng.shape[-1]
    num_mun = x_train_eng.shape[1]
    
    model = LSTMModel(input_dim, output_dim, hidden=64).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    model.train()
    for ep in range(80):
        for t in range(lookback, x_train_eng.shape[0] - 1):
            seq = torch.tensor(x_train_eng[t-lookback:t], dtype=torch.float32).to(device)
            seq = seq.permute(1, 0, 2)  # (mun, lookback, feat)
            target = torch.tensor(x_train_raw[t, :, :output_dim], dtype=torch.float32).to(device)
            pred = model(seq)
            loss = F.mse_loss(pred, target)
            opt.zero_grad(); loss.backward(); opt.step()
    
    model.eval()
    preds = []
    t0 = time.time()
    with torch.no_grad():
        for t in range(lookback, x_test_eng.shape[0] - 1):
            seq = torch.tensor(x_test_eng[t-lookback:t], dtype=torch.float32).to(device)
            seq = seq.permute(1, 0, 2)
            preds.append(model(seq).cpu().numpy())
    t_ms = (time.time() - t0) * 1000 / max(len(preds), 1)
    
    if preds:
        y_pred = np.stack(preds)
        y_true = x_test_raw[lookback+1:x_test_eng.shape[0], :, :output_dim]
        min_len = min(len(y_pred), len(y_true))
        return compute_metrics(y_true[:min_len], y_pred[:min_len]), t_ms
    return {"rmse": 1.0, "mae": 1.0, "r2": 0.0, "f1_score": 0.0, "precision": 0.0, "recall": 0.0}, 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 75)
    print("TASK-083 v4: NeKo-PIGNN Otimizado para Dados Reais")
    print("  Melhorias: Feature Eng + Residual Learning + Ensemble + Adj Correlação")
    print("=" * 75)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    
    # Load data
    print("\n[1/6] Carregando e preparando dados...")
    x_raw, x_eng, adj, lookback, stats = load_and_prepare()
    
    OUTPUT_DIM = 6  # prediz todas as features
    
    # Split — nota: x_eng tem lookback dias a menos que x_raw
    tr_raw, val_raw, te_raw = temporal_split(x_raw)
    tr_eng, val_eng, te_eng = temporal_split(x_eng)
    
    # Alinhar raw com eng (eng começa no dia lookback do raw)
    # x_eng[i] corresponde a x_raw[i + lookback]
    tr_raw_aligned = tr_raw[lookback:]
    te_raw_aligned = te_raw[lookback:]
    
    # Truncar eng ao tamanho do raw alinhado
    min_tr = min(tr_eng.shape[0], tr_raw_aligned.shape[0])
    min_te = min(te_eng.shape[0], te_raw_aligned.shape[0])
    tr_eng = tr_eng[:min_tr]
    tr_raw_aligned = tr_raw_aligned[:min_tr]
    te_eng = te_eng[:min_te]
    te_raw_aligned = te_raw_aligned[:min_te]
    
    print(f"  Train: {tr_eng.shape[0]}d | Test: {te_eng.shape[0]}d | Features: {x_eng.shape[-1]}")
    
    results = []
    
    # MLP Residual + Feature Engineering
    print("\n[2/6] MLP Residual + Feature Engineering...")
    m, t = train_eval_mlp_residual(tr_eng, te_eng, tr_raw_aligned, te_raw_aligned, OUTPUT_DIM, device)
    results.append({"model": "MLP-Residual+FeatEng", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # XGBoost + Feature Engineering
    print("\n[3/6] XGBoost + Feature Engineering...")
    m, t = train_eval_xgboost(tr_eng, te_eng, tr_raw_aligned, te_raw_aligned, OUTPUT_DIM)
    results.append({"model": "XGBoost+FeatEng", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # LSTM + Feature Engineering
    print("\n[4/6] LSTM + Feature Engineering...")
    m, t = train_eval_lstm(tr_eng, te_eng, tr_raw_aligned, te_raw_aligned, OUTPUT_DIM, device)
    results.append({"model": "LSTM+FeatEng", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # NeKo-PIGNN v4
    print("\n[5/6] NeKo-PIGNN v4 (Residual + GNN + Ensemble + Adj Correlação)...")
    m, t = train_eval_neko_v4(tr_eng, te_eng, tr_raw_aligned, te_raw_aligned, adj, OUTPUT_DIM, device)
    results.append({"model": "NeKo-PIGNN v4 (ours)", **m, "inference_ms": t})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # Persistence Baseline
    print("\n[6/6] Persistence Baseline (naive)...")
    y_true = te_raw_aligned[1:]
    y_persist = te_raw_aligned[:-1]
    min_l = min(len(y_true), len(y_persist))
    m = compute_metrics(y_true[:min_l], y_persist[:min_l])
    results.append({"model": "Persistence (naive)", **m, "inference_ms": 0.0})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # Resultados
    print("\n" + "=" * 80)
    print("RESULTADOS v4 — DADOS REAIS OTIMIZADOS")
    print("=" * 80)
    print(f"{'Model':<28} {'RMSE':<8} {'MAE':<8} {'R²':<8} {'F1':<8} {'Prec':<8} {'Rec':<8}")
    print("-" * 80)
    for r in results:
        print(f"{r['model']:<28} {r['rmse']:<8.4f} {r['mae']:<8.4f} {r['r2']:<8.4f} {r['f1_score']:<8.4f} {r['precision']:<8.4f} {r['recall']:<8.4f}")
    
    # Comparação com v3
    print("\n--- Comparação com v3 (sem feature engineering) ---")
    with open(RESULTS_DIR / "benchmark_results_real.json") as f:
        v3 = json.load(f)
    for r3 in v3["results"]:
        print(f"  v3 {r3['model']:<22} RMSE={r3['rmse']:.4f} R²={r3['r2']:.4f}")
    
    # Salvar
    output = {
        "experiment": "TASK-083 v4 — Optimized Real Data",
        "date": "2026-06-08",
        "improvements": [
            "Feature engineering (lag-3, rolling mean/std)",
            "Residual learning (predict Δx)",
            "Ensemble head (Koopman + GNN + Persistence)",
            "Adjacency weighted by fire correlation",
            "Spectral regularization",
            "Data augmentation (jitter)",
        ],
        "config": {
            "num_municipalities": x_raw.shape[1],
            "num_days_raw": x_raw.shape[0],
            "features_raw": 6,
            "features_engineered": x_eng.shape[-1],
            "lookback": lookback,
            "output_dim": OUTPUT_DIM,
        },
        "results": results,
    }
    
    json_path = RESULTS_DIR / "benchmark_results_v4.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ JSON: {json_path}")
    print("\n🎉 Experimento v4 concluído!")


if __name__ == "__main__":
    main()
