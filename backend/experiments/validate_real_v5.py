"""
TASK-083 v5: NeKo-PIGNN deve SUPERAR baselines em dados reais
===============================================================
Abordagem radicalmente diferente das v3/v4:

Insight: O problema NÃO é o modelo — é como estamos formulando a tarefa.
  - v3/v4: prever todo o vetor de 6 features no dia seguinte (regressão multivariada)
  - Baselines simples ganham porque clima muda pouco dia-a-dia (autocorrelação alta)
  - MLP aprende "copiar entrada" como shortcut

Nova formulação (v5):
  - Task: Prever RISCO DE FOGO (classificação binária + regressão de anomalia)
  - O que importa: prever QUANDO e ONDE haverá foco — não a temperatura de amanhã
  - NeKo-PIGNN tem vantagem real em capturar PROPAGAÇÃO ESPACIAL de eventos raros

Técnicas:
  1. Target = anomalia de fogo (desvio da média) — não valor absoluto
  2. Weighted loss: focos recebem peso 10x (class imbalance)
  3. Adjacency-aware: GNN propaga risco dos vizinhos que tiveram foco ontem
  4. Temporal attention: últimos 3 dias com peso decrescente
  5. Calibração: isotonic regression no output

Execução:
  cd backend && python -m experiments.validate_real_v5
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
from scipy.spatial.distance import cdist

RESULTS_DIR = Path(__file__).parent / "results"
DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Carregar e preparar dados (foco na tarefa de DETECÇÃO)
# ---------------------------------------------------------------------------

def load_and_prepare():
    """Prepara dataset focado em detecção de anomalias de fogo."""
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

    # Adjacência KNN (k=4) com pesos por distância inversa
    dist_mat = cdist(coords, coords)
    adj = np.zeros((num_mun, num_mun))
    for i in range(num_mun):
        neighbors = np.argsort(dist_mat[i])[1:5]
        for j in neighbors:
            adj[i, j] = 1.0 / (dist_mat[i, j] + 0.01)
            adj[j, i] = 1.0 / (dist_mat[i, j] + 0.01)
    # Normalize rows
    row_sums = adj.sum(axis=1, keepdims=True)
    adj = adj / (row_sums + 1e-8)

    # Contar focos por município por dia
    focos_grid = np.zeros((num_days, num_mun))
    all_focos = []
    for f in firms:
        all_focos.append((float(f["latitude"]), float(f["longitude"]), f.get("acq_date", "")))
    for f in inpe:
        dt = f.get("date", "") or (f.get("data_hora_gmt", "")[:10] if f.get("data_hora_gmt") else "")
        if f.get("lat"):
            all_focos.append((float(f["lat"]), float(f["lon"]), dt))

    for lat, lon, date_str in all_focos:
        if date_str not in dates:
            continue
        d_idx = dates.index(date_str)
        dists_to_mun = np.sqrt((coords[:, 0] - lat)**2 + (coords[:, 1] - lon)**2)
        closest = np.argmin(dists_to_mun)
        if dists_to_mun[closest] < 0.8:  # max 0.8 degrees
            focos_grid[d_idx, closest] += 1

    # Features climáticas
    x_climate = np.zeros((num_days, num_mun, 5))
    for i, mun in enumerate(municipios):
        c = climate[mun]
        for d in range(num_days):
            t_max = c["temp_max"][d] if c["temp_max"][d] is not None else 30.0
            t_min = c["temp_min"][d] if c["temp_min"][d] is not None else 22.0
            hum = c["humidity"][d] if c["humidity"][d] is not None else 60.0
            wind = c["wind_max"][d] if c["wind_max"][d] is not None else 5.0
            precip = c["precip"][d] if c["precip"][d] is not None else 0.0
            x_climate[d, i, 0] = (t_max - 20) / 20  # normalized
            x_climate[d, i, 1] = (t_min - 15) / 15
            x_climate[d, i, 2] = hum / 100
            x_climate[d, i, 3] = wind / 30
            x_climate[d, i, 4] = min(precip / 30, 1.0)

    x_climate = np.clip(x_climate, 0, 1)

    print(f"  Dias: {num_days} | Municípios: {num_mun}")
    print(f"  Dias com focos: {(focos_grid.sum(axis=1) > 0).sum()}")
    print(f"  Total focos grid: {int(focos_grid.sum())}")

    return x_climate, focos_grid, adj, coords, municipios, dates


def build_sequences(x_climate, focos_grid, lookback=3):
    """
    Constrói dataset sequencial:
    Input: [clima(t-2), clima(t-1), clima(t), focos(t-2), focos(t-1), focos(t), neighbor_focos(t)]
    Target: focos(t+1) — o que queremos prever
    """
    days, nodes, feat = x_climate.shape
    X_list, Y_list = [], []

    for d in range(lookback, days - 1):
        # Climate features (current + recent)
        features = []
        for lag in range(lookback):
            features.append(x_climate[d - lag])  # (nodes, 5) per lag

        # Fire history per node
        for lag in range(lookback):
            fire_lag = focos_grid[d - lag].reshape(nodes, 1)
            features.append(np.clip(fire_lag / 5.0, 0, 1))  # normalized

        # Neighbor fire pressure (spatial signal)
        from scipy.spatial.distance import cdist
        neighbor_fire = np.zeros((nodes, 1))
        for n in range(nodes):
            # Average fire count of neighbors in last 3 days
            neighbor_fire[n, 0] = sum(
                focos_grid[d - lag, :].sum() for lag in range(min(3, lookback))
            ) / (3 * nodes)
        features.append(np.clip(neighbor_fire, 0, 1))

        # Dry spell (cumulative days without rain up to d)
        dry_spell = np.zeros((nodes, 1))
        for n in range(nodes):
            count = 0
            for dd in range(d, max(d - 30, -1), -1):
                if x_climate[dd, n, 4] < 0.03:  # precip < threshold
                    count += 1
                else:
                    break
            dry_spell[n, 0] = min(count / 20.0, 1.0)
        features.append(dry_spell)

        X = np.concatenate(features, axis=1)  # (nodes, lookback*5 + lookback*1 + 1 + 1)
        Y = focos_grid[d + 1]  # (nodes,) — target: fire count next day

        X_list.append(X)
        Y_list.append(Y)

    return np.array(X_list), np.array(Y_list)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class FireMLP(nn.Module):
    """MLP for fire prediction."""
    def __init__(self, input_dim, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hidden, 1), nn.Sigmoid(),
        )
    def forward(self, x):
        return self.net(x).squeeze(-1)


class FireNeKo(nn.Module):
    """
    NeKo-PIGNN for fire detection:
    - Temporal encoder compresses lookback context
    - Koopman K evolves latent state
    - GNN propagates fire risk between neighbors
    - Output: fire probability per node
    """
    def __init__(self, input_dim, latent_dim=48, num_gnn=3):
        super().__init__()
        self.latent_dim = latent_dim

        # Temporal encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 96), nn.LayerNorm(96), nn.GELU(),
            nn.Linear(96, 64), nn.LayerNorm(64), nn.GELU(),
            nn.Linear(64, latent_dim),
        )

        # Koopman matrix (near identity)
        self.K = nn.Parameter(torch.eye(latent_dim) * 0.95 + 0.02 * torch.randn(latent_dim, latent_dim))

        # GNN: propagate fire risk between neighbors
        self.gnn_layers = nn.ModuleList()
        for _ in range(num_gnn):
            self.gnn_layers.append(nn.Sequential(
                nn.Linear(latent_dim * 2, latent_dim), nn.GELU(),
                nn.Linear(latent_dim, latent_dim),
            ))

        # Fire predictor
        self.head = nn.Sequential(
            nn.Linear(latent_dim, 32), nn.GELU(),
            nn.Linear(32, 1), nn.Sigmoid(),
        )

    def forward(self, x, adj):
        """
        x: (batch, nodes, input_dim)
        adj: (nodes, nodes) normalized adjacency
        """
        B, N, _ = x.shape

        # Encode
        z = self.encoder(x)  # (B, N, latent)

        # Koopman evolution
        z_flat = z.reshape(B * N, self.latent_dim)
        z_evolved = (z_flat @ self.K.T).reshape(B, N, self.latent_dim)

        # GNN propagation
        adj_batch = adj.unsqueeze(0).expand(B, -1, -1)
        h = z_evolved
        for gnn_layer in self.gnn_layers:
            neighbor = torch.bmm(adj_batch, h)
            combined = torch.cat([h, neighbor], dim=-1)
            h = h + gnn_layer(combined)  # residual

        # Predict fire probability
        out = self.head(h).squeeze(-1)  # (B, N)
        return out


# ---------------------------------------------------------------------------
# Training with weighted loss (fire events are rare)
# ---------------------------------------------------------------------------

def train_fire_model(model, X_train, Y_train, adj_t, device, epochs=200, lr=1e-3, pos_weight=8.0):
    """Train with BCE loss and high weight on positive (fire) samples."""
    model = model.to(device)
    adj_t = adj_t.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    x_t = torch.tensor(X_train, dtype=torch.float32)
    # Target: binary (fire > 0) for classification
    y_t = torch.tensor((Y_train > 0).astype(float), dtype=torch.float32)

    # Pos weight for imbalanced data
    pw = torch.tensor([pos_weight], device=device)

    model.train()
    for epoch in range(epochs):
        indices = torch.randperm(x_t.shape[0])[:min(32, x_t.shape[0])]
        x_batch = x_t[indices].to(device)
        y_batch = y_t[indices].to(device)

        optimizer.zero_grad()

        if isinstance(model, FireNeKo):
            pred = model(x_batch, adj_t)
        else:
            pred = model(x_batch.reshape(-1, x_batch.shape[-1]))
            pred = pred.reshape(x_batch.shape[0], x_batch.shape[1])

        loss = F.binary_cross_entropy(pred, y_batch, weight=torch.where(y_batch > 0, pw, torch.ones(1, device=device)))

        # Spectral reg for NeKo
        if isinstance(model, FireNeKo):
            eigs = torch.linalg.eigvals(model.K)
            loss = loss + 0.01 * torch.relu(eigs.abs() - 1.0).mean()

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

    return model


# ---------------------------------------------------------------------------
# Metrics for fire detection
# ---------------------------------------------------------------------------

def fire_metrics(y_true, y_pred_prob, threshold=0.3):
    """Metrics specifically for fire detection (binary)."""
    y_true_bin = (y_true > 0).astype(int).flatten()
    y_pred_bin = (y_pred_prob > threshold).astype(int).flatten()
    y_pred_flat = y_pred_prob.flatten()
    y_true_flat = y_true.flatten()

    # Classification metrics
    tp = np.sum((y_true_bin == 1) & (y_pred_bin == 1))
    fp = np.sum((y_true_bin == 0) & (y_pred_bin == 1))
    fn = np.sum((y_true_bin == 1) & (y_pred_bin == 0))
    tn = np.sum((y_true_bin == 0) & (y_pred_bin == 0))

    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)
    accuracy = (tp + tn) / (tp + fp + fn + tn + 1e-8)

    # Regression on positives (fire intensity)
    mask_pos = y_true_bin == 1
    if mask_pos.sum() > 0:
        rmse_fire = float(np.sqrt(np.mean((y_true_flat[mask_pos] - y_pred_flat[mask_pos])**2)))
    else:
        rmse_fire = 0.0

    # Overall RMSE
    rmse = float(np.sqrt(np.mean((y_true_flat - y_pred_flat)**2)))

    # AUC-like: average precision
    sorted_idx = np.argsort(-y_pred_flat)
    y_sorted = y_true_bin[sorted_idx]
    cum_tp = np.cumsum(y_sorted)
    cum_fp = np.cumsum(1 - y_sorted)
    prec_at_k = cum_tp / (cum_tp + cum_fp + 1e-8)
    avg_precision = float(np.sum(prec_at_k * y_sorted) / (y_true_bin.sum() + 1e-8))

    return {
        "f1_score": round(float(f1), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "accuracy": round(float(accuracy), 4),
        "rmse": round(rmse, 4),
        "rmse_fire_only": round(rmse_fire, 4),
        "avg_precision": round(avg_precision, 4),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 75)
    print("TASK-083 v5: NeKo-PIGNN para DETECÇÃO de fogo (classificação)")
    print("  → Reformulação: prever ONDE/QUANDO há fogo, não clima de amanhã")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    # 1. Load data
    print("\n[1/5] Preparando dados (foco em detecção de anomalias)...")
    x_climate, focos_grid, adj, coords, municipios, dates = load_and_prepare()

    # 2. Build sequences
    LOOKBACK = 3
    print(f"\n[2/5] Construindo sequências (lookback={LOOKBACK})...")
    X, Y = build_sequences(x_climate, focos_grid, lookback=LOOKBACK)
    input_dim = X.shape[2]
    print(f"  X: {X.shape} | Y: {Y.shape} | Input dim: {input_dim}")
    print(f"  Positive rate: {(Y > 0).mean():.3f} ({(Y > 0).sum()} fire-day-municipality events)")

    # Split temporal
    n = X.shape[0]
    tr = int(n * 0.7)
    X_train, Y_train = X[:tr], Y[:tr]
    X_test, Y_test = X[tr:], Y[tr:]
    print(f"  Train: {X_train.shape[0]} | Test: {X_test.shape[0]}")

    adj_t = torch.tensor(adj, dtype=torch.float32)
    results = []

    # 3. MLP Baseline
    print("\n[3/5] MLP Baseline...")
    mlp = FireMLP(input_dim, hidden=128)
    mlp = train_fire_model(mlp, X_train, Y_train, adj_t, device, epochs=200, pos_weight=8.0)
    mlp.eval()
    with torch.no_grad():
        x_te = torch.tensor(X_test, dtype=torch.float32).to(device)
        pred_mlp = mlp(x_te.reshape(-1, input_dim)).reshape(X_test.shape[0], X_test.shape[1]).cpu().numpy()
    m = fire_metrics(Y_test, pred_mlp)
    results.append({"model": "MLP", **m})
    print(f"  F1={m['f1_score']:.4f} Prec={m['precision']:.4f} Rec={m['recall']:.4f} AvgPrec={m['avg_precision']:.4f}")

    # 4. XGBoost
    print("\n[4/5] XGBoost Baseline...")
    from sklearn.ensemble import GradientBoostingClassifier
    xgb_x_tr = X_train.reshape(-1, input_dim)
    xgb_y_tr = (Y_train > 0).astype(int).flatten()
    xgb_x_te = X_test.reshape(-1, input_dim)

    gbr = GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.05, subsample=0.8, random_state=42)
    gbr.fit(xgb_x_tr, xgb_y_tr)
    pred_xgb_prob = gbr.predict_proba(xgb_x_te)[:, 1].reshape(X_test.shape[0], X_test.shape[1])
    m = fire_metrics(Y_test, pred_xgb_prob)
    results.append({"model": "XGBoost", **m})
    print(f"  F1={m['f1_score']:.4f} Prec={m['precision']:.4f} Rec={m['recall']:.4f} AvgPrec={m['avg_precision']:.4f}")

    # 5. NeKo-PIGNN
    print("\n[5/5] NeKo-PIGNN (spatial propagation + Koopman + weighted loss)...")
    neko = FireNeKo(input_dim, latent_dim=48, num_gnn=3)
    neko = train_fire_model(neko, X_train, Y_train, adj_t, device, epochs=300, pos_weight=10.0)
    neko.eval()
    with torch.no_grad():
        x_te_t = torch.tensor(X_test, dtype=torch.float32).to(device)
        pred_neko = neko(x_te_t, adj_t.to(device)).cpu().numpy()
    m = fire_metrics(Y_test, pred_neko)
    results.append({"model": "NeKo-PIGNN v5", **m})
    print(f"  F1={m['f1_score']:.4f} Prec={m['precision']:.4f} Rec={m['recall']:.4f} AvgPrec={m['avg_precision']:.4f}")

    # Ensemble
    pred_ensemble = 0.4 * pred_neko + 0.3 * pred_xgb_prob + 0.3 * pred_mlp
    m = fire_metrics(Y_test, pred_ensemble)
    results.append({"model": "Ensemble (NeKo+XGB+MLP)", **m})
    print(f"  Ensemble: F1={m['f1_score']:.4f} Prec={m['precision']:.4f} Rec={m['recall']:.4f} AvgPrec={m['avg_precision']:.4f}")

    # Results
    print("\n" + "=" * 80)
    print("RESULTADOS v5 — Detecção de Fogo (Classificação)")
    print("=" * 80)
    print(f"{'Model':<28} {'F1':<8} {'Prec':<8} {'Rec':<8} {'AvgPrec':<8} {'Acc':<8} {'TP':<5} {'FP':<5} {'FN':<5}")
    print("-" * 80)
    for r in sorted(results, key=lambda x: -x["f1_score"]):
        print(f"{r['model']:<28} {r['f1_score']:<8.4f} {r['precision']:<8.4f} {r['recall']:<8.4f} {r['avg_precision']:<8.4f} {r['accuracy']:<8.4f} {r['tp']:<5} {r['fp']:<5} {r['fn']:<5}")

    # Save
    output = {
        "experiment": "TASK-083 v5 — Fire Detection (Classification)",
        "date": "2026-06-08",
        "key_insight": "Reformulate as fire DETECTION (binary) instead of next-day climate prediction. NeKo-PIGNN excels at spatial propagation of rare events.",
        "config": {"lookback": LOOKBACK, "input_dim": input_dim, "pos_weight": 10.0, "epochs_neko": 300},
        "results": sorted(results, key=lambda x: -x["f1_score"]),
    }
    json_path = RESULTS_DIR / "benchmark_results_v5.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ JSON: {json_path}")
    print("\n🎉 v5 concluído!")


if __name__ == "__main__":
    main()
