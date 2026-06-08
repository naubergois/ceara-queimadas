"""
TASK-083 v3: Experimento com Dados REAIS (NASA FIRMS + INPE + Open-Meteo)
==========================================================================
Dados coletados:
  - NASA FIRMS: 128 focos VIIRS/MODIS (7 dias)
  - INPE BDQueimadas: 249 focos (30 dias com dados)
  - Open-Meteo: 97 dias × 15 municípios (clima)

Abordagem:
  - Construir série temporal diária por município (15 nós × 90+ dias)
  - Features: temp_max, temp_min, umidade, vento, precipitação, focos_dia
  - Target: número de focos no dia seguinte (regressão) ou presença (binário)
  - Comparar modelos: MLP, LSTM, XGBoost, Koopman-Det, NeKo-PIGNN v2

Execução:
  cd backend && python -m experiments.validate_real_data
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# Reutiliza modelos da v2
from experiments.validate_models_v2 import (
    DeterministicKoopman, NeKoPIGNN_v2, SimpleGNNLayer,
    MLPBaseline, LSTMBaseline, train_xgboost_baseline,
    compute_metrics, generate_latex_table,
    train_neko_v2_curriculum,
)

RESULTS_DIR = Path(__file__).parent / "results"
DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Carregar e preparar dados reais
# ---------------------------------------------------------------------------


def load_real_data():
    """Carrega dados reais e constrói dataset temporal por município."""
    
    # 1. Carregar clima
    with open(DATA_DIR / "climate_ceara_90d.json") as f:
        climate = json.load(f)
    
    # 2. Carregar focos FIRMS
    firms_path = DATA_DIR / "firms_ceara_7d.json"
    if firms_path.exists():
        with open(firms_path) as f:
            focos_firms = json.load(f)
    else:
        focos_firms = []
    
    # 3. Carregar focos INPE
    inpe_path = DATA_DIR / "inpe_ceara_historico.json"
    if inpe_path.exists():
        with open(inpe_path) as f:
            focos_inpe = json.load(f)
    else:
        focos_inpe = []
    
    print(f"  Clima: {len(climate)} municípios × {len(next(iter(climate.values()))['dates'])} dias")
    print(f"  FIRMS: {len(focos_firms)} focos")
    print(f"  INPE: {len(focos_inpe)} focos")
    
    return climate, focos_firms, focos_inpe


def build_daily_dataset(climate, focos_firms, focos_inpe):
    """
    Constrói dataset: (dias × municípios × features)
    Features: [temp_max_norm, temp_min_norm, humidity_norm, wind_norm, precip_norm, focos_count]
    """
    municipios = list(climate.keys())
    num_mun = len(municipios)
    
    # Datas disponíveis no clima
    dates = climate[municipios[0]]["dates"]
    num_days = len(dates)
    
    # Coordenadas dos municípios
    coords = np.array([[climate[m]["lat"], climate[m]["lon"]] for m in municipios])
    
    # Contar focos por município por dia
    focos_por_mun_dia = defaultdict(lambda: defaultdict(int))
    
    # Mapear foco → município mais próximo
    def closest_mun(lat, lon):
        dists = np.sqrt((coords[:, 0] - lat)**2 + (coords[:, 1] - lon)**2)
        return municipios[np.argmin(dists)]
    
    # FIRMS focos
    for f in focos_firms:
        try:
            lat = float(f.get("latitude", 0))
            lon = float(f.get("longitude", 0))
            date = f.get("acq_date", "")
            mun = closest_mun(lat, lon)
            focos_por_mun_dia[mun][date] += 1
        except:
            pass
    
    # INPE focos
    for f in focos_inpe:
        try:
            lat = float(f.get("lat", 0))
            lon = float(f.get("lon", 0))
            date = f.get("date", "")
            if not date:
                # Extrair da data_hora_gmt
                dt_str = f.get("data_hora_gmt", "")
                if dt_str:
                    date = dt_str[:10]
            mun = closest_mun(lat, lon)
            focos_por_mun_dia[mun][date] += 1
        except:
            pass
    
    # Construir tensor: (num_days, num_mun, 6)
    # Features: temp_max, temp_min, humidity, wind, precip, focos
    x_data = np.zeros((num_days, num_mun, 6))
    
    for i, mun in enumerate(municipios):
        c = climate[mun]
        for d in range(num_days):
            date_str = dates[d]
            
            temp_max = c["temp_max"][d] if c["temp_max"][d] is not None else 30.0
            temp_min = c["temp_min"][d] if c["temp_min"][d] is not None else 22.0
            humidity = c["humidity"][d] if c["humidity"][d] is not None else 60.0
            wind = c["wind_max"][d] if c["wind_max"][d] is not None else 5.0
            precip = c["precip"][d] if c["precip"][d] is not None else 0.0
            focos = focos_por_mun_dia[mun].get(date_str, 0)
            
            x_data[d, i, 0] = temp_max
            x_data[d, i, 1] = temp_min
            x_data[d, i, 2] = humidity
            x_data[d, i, 3] = wind
            x_data[d, i, 4] = precip
            x_data[d, i, 5] = focos
    
    # Normalização min-max por feature
    feature_stats = {}
    for f_idx in range(6):
        fmin = x_data[:, :, f_idx].min()
        fmax = x_data[:, :, f_idx].max()
        feature_stats[f_idx] = {"min": float(fmin), "max": float(fmax)}
        if fmax > fmin:
            x_data[:, :, f_idx] = (x_data[:, :, f_idx] - fmin) / (fmax - fmin)
        else:
            x_data[:, :, f_idx] = 0.0
    
    # Adjacência (KNN dos municípios reais)
    from scipy.spatial.distance import cdist
    dist_matrix = cdist(coords, coords)
    adj = np.zeros((num_mun, num_mun))
    for i in range(num_mun):
        neighbors = np.argsort(dist_matrix[i])[1:5]
        adj[i, neighbors] = 1
        adj[neighbors, i] = 1
    
    print(f"  Dataset: {x_data.shape} (dias × municípios × features)")
    print(f"  Total focos no período: {int(x_data[:,:,5].sum() * (feature_stats[5]['max'] - feature_stats[5]['min']) + x_data.shape[0] * x_data.shape[1] * feature_stats[5]['min'])}")
    print(f"  Dias com focos: {(x_data[:,:,5].sum(axis=1) > 0).sum()}")
    print(f"  Adjacência density: {adj.sum() / (num_mun**2):.2f}")
    
    return (
        torch.tensor(x_data, dtype=torch.float32),
        torch.tensor(adj, dtype=torch.float32),
        municipios,
        dates,
        feature_stats,
    )


# ---------------------------------------------------------------------------
# Split temporal
# ---------------------------------------------------------------------------


def temporal_split(x, train_ratio=0.7, val_ratio=0.1):
    n = x.shape[0]
    tr = int(n * train_ratio)
    va = int(n * (train_ratio + val_ratio))
    return {
        "train": x[:tr],
        "val": x[tr:va],
        "test": x[va:],
    }


# ---------------------------------------------------------------------------
# Avaliação
# ---------------------------------------------------------------------------


def evaluate_neko(model, x_test, adj, device):
    model.eval()
    adj_d = adj.to(device)
    preds = []
    t0 = time.time()
    with torch.no_grad():
        for t in range(x_test.shape[0] - 1):
            x_t = x_test[t:t+1].to(device)
            out = model(x_t, adj_d)
            preds.append(out["x_pred"].cpu())
    inf_time = (time.time() - t0) * 1000 / max(len(preds), 1)
    y_pred = torch.cat(preds).numpy()
    y_true = x_test[1:].numpy()
    return compute_metrics(y_true, y_pred), inf_time


def evaluate_koopman_det(model, x_test, device):
    model.eval()
    x_flat_t = x_test[:-1].reshape(-1, x_test.shape[-1])
    x_flat_tp1 = x_test[1:].reshape(-1, x_test.shape[-1])
    t0 = time.time()
    with torch.no_grad():
        out = model(x_flat_t.to(device), x_flat_tp1.to(device))
        y_pred = out["preds"][0].cpu().numpy()
    inf_time = (time.time() - t0) * 1000 / x_flat_t.shape[0] * x_test.shape[1]
    return compute_metrics(x_flat_tp1.numpy(), y_pred), inf_time


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 75)
    print("TASK-083 v3: Experimento com DADOS REAIS")
    print("  Fontes: NASA FIRMS + INPE BDQueimadas + Open-Meteo")
    print("=" * 75)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    
    # 1. Carregar dados
    print("\n[1/8] Carregando dados reais...")
    climate, focos_firms, focos_inpe = load_real_data()
    
    # 2. Construir dataset
    print("\n[2/8] Construindo dataset temporal (dias × municípios × features)...")
    x_data, adj, municipios, dates, feature_stats = build_daily_dataset(climate, focos_firms, focos_inpe)
    
    NUM_DAYS = x_data.shape[0]
    NUM_MUN = x_data.shape[1]
    INPUT_DIM = x_data.shape[2]
    
    # 3. Split
    splits = temporal_split(x_data)
    x_train = splits["train"]
    x_val = splits["val"]
    x_test = splits["test"]
    print(f"\n[3/8] Split: Train={x_train.shape[0]}d | Val={x_val.shape[0]}d | Test={x_test.shape[0]}d")
    
    results = []
    
    # 4. MLP Baseline
    print("\n[4/8] MLP Baseline (256 hidden, 100 epochs)...")
    x_tr_flat = x_train[:-1].reshape(-1, INPUT_DIM)
    y_tr_flat = x_train[1:].reshape(-1, INPUT_DIM)
    x_te_flat = x_test[:-1].reshape(-1, INPUT_DIM)
    y_te_flat = x_test[1:].reshape(-1, INPUT_DIM)
    
    mlp = MLPBaseline(INPUT_DIM, 256).to(device)
    opt = torch.optim.Adam(mlp.parameters(), lr=1e-3)
    dataset = TensorDataset(x_tr_flat, y_tr_flat)
    loader = DataLoader(dataset, batch_size=128, shuffle=True)
    mlp.train()
    for epoch in range(100):
        for xb, yb in loader:
            loss = F.mse_loss(mlp(xb.to(device)), yb.to(device))
            opt.zero_grad(); loss.backward(); opt.step()
    mlp.eval()
    t0 = time.time()
    with torch.no_grad():
        y_pred_mlp = mlp(x_te_flat.to(device)).cpu().numpy()
    t_mlp = (time.time() - t0) * 1000 / x_te_flat.shape[0] * NUM_MUN
    m = compute_metrics(y_te_flat.numpy(), y_pred_mlp)
    results.append({"model": "MLP", **m, "inference_ms": t_mlp})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 5. LSTM
    print("\n[5/8] LSTM (128 hidden, lookback=5)...")
    lookback = 5
    lstm = LSTMBaseline(INPUT_DIM, 128, 2).to(device)
    opt = torch.optim.Adam(lstm.parameters(), lr=1e-3)
    lstm.train()
    for epoch in range(60):
        for t in range(lookback, x_train.shape[0]):
            seq = x_train[t-lookback:t].to(device).permute(1, 0, 2)  # (mun, lookback, feat)
            target = x_train[t].to(device)
            pred = lstm(seq)
            loss = F.mse_loss(pred, target)
            opt.zero_grad(); loss.backward(); opt.step()
    
    lstm.eval()
    preds_lstm = []
    t0 = time.time()
    with torch.no_grad():
        for t in range(lookback, x_test.shape[0]):
            seq = x_test[t-lookback:t].to(device).permute(1, 0, 2)
            preds_lstm.append(lstm(seq).cpu())
    t_lstm = (time.time() - t0) * 1000 / max(len(preds_lstm), 1)
    if preds_lstm:
        y_pred_lstm = torch.stack(preds_lstm).numpy()
        y_true_lstm = x_test[lookback:].numpy()
        m = compute_metrics(y_true_lstm, y_pred_lstm)
    else:
        m = {"rmse": 1.0, "mae": 1.0, "r2": 0.0, "f1_score": 0.0, "precision": 0.0, "recall": 0.0}
    results.append({"model": "LSTM", **m, "inference_ms": t_lstm})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 6. XGBoost
    print("\n[6/8] XGBoost (200 trees)...")
    x_tr_np = x_train[:-1].numpy()
    y_tr_np = x_train[1:].numpy()
    x_te_np = x_test[:-1].numpy()
    y_te_np = x_test[1:].numpy()
    t0 = time.time()
    y_pred_xgb = train_xgboost_baseline(x_tr_np, y_tr_np, x_te_np)
    t_xgb = (time.time() - t0) * 1000 / max(x_te_np.shape[0] * NUM_MUN, 1)
    m = compute_metrics(y_te_np, y_pred_xgb)
    results.append({"model": "XGBoost", **m, "inference_ms": t_xgb})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 7. Koopman Determinístico
    print("\n[7/8] Koopman Determinístico (latent=64, 200 epochs)...")
    koopman = DeterministicKoopman(input_dim=INPUT_DIM, latent_dim=64).to(device)
    opt = torch.optim.AdamW(koopman.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=200)
    koopman.train()
    for epoch in range(200):
        indices = torch.randperm(x_train.shape[0] - 3)[:min(64, x_train.shape[0] - 3)]
        for idx in indices:
            x_t = x_train[idx].reshape(-1, INPUT_DIM).to(device)
            x_tp1 = x_train[idx + 1].reshape(-1, INPUT_DIM).to(device)
            out = koopman(x_t, x_tp1)
            # Multi-step
            z = koopman.encode(x_t)
            ml = torch.tensor(0.0, device=device)
            z_c = z
            for s in range(1, 4):
                z_c = koopman.forward_k(z_c)
                if idx + s < x_train.shape[0]:
                    tgt = x_train[idx + s].reshape(-1, INPUT_DIM).to(device)
                    ml = ml + F.mse_loss(koopman.decode(z_c), tgt) * (0.7**s)
            loss = out["loss"] + 0.5 * ml
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(koopman.parameters(), 1.0)
            opt.step()
        sched.step()
    
    m, t_koop = evaluate_koopman_det(koopman, x_test, device)
    results.append({"model": "Koopman-Det (ours)", **m, "inference_ms": t_koop})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # 8. NeKo-PIGNN v2 com Curriculum Learning
    print("\n[8/8] NeKo-PIGNN v2 (Curriculum Learning, 100+150 epochs)...")
    neko = NeKoPIGNN_v2(input_dim=INPUT_DIM, latent_dim=64, num_gnn_layers=3)
    history = train_neko_v2_curriculum(neko, x_train, adj, device, epochs_phase1=100, epochs_phase2=150)
    m, t_neko = evaluate_neko(neko, x_test, adj, device)
    results.append({"model": "NeKo-PIGNN v2 (ours)", **m, "inference_ms": t_neko})
    print(f"  RMSE={m['rmse']:.4f} R²={m['r2']:.4f} F1={m['f1_score']:.4f}")
    
    # ---------------------------------------------------------------------------
    # Resultados
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("RESULTADOS — DADOS REAIS (NASA FIRMS + INPE + Open-Meteo)")
    print("=" * 75)
    print(f"{'Model':<25} {'RMSE':<8} {'MAE':<8} {'R²':<8} {'F1':<8} {'Recall':<8} {'ms':<6}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<25} {r['rmse']:<8.4f} {r['mae']:<8.4f} {r['r2']:<8.4f} {r['f1_score']:<8.4f} {r['recall']:<8.4f} {r['inference_ms']:<6.1f}")
    
    # Salvar
    output = {
        "experiment": "TASK-083 v3 — Real Data Validation",
        "date": "2026-06-08",
        "data_sources": {
            "nasa_firms": f"{len(focos_firms)} focos (7 days, VIIRS+MODIS)",
            "inpe": f"{len(focos_inpe)} focos (30 days)",
            "open_meteo": f"{len(climate)} municípios × 97 days",
        },
        "config": {
            "num_municipalities": NUM_MUN,
            "num_days": NUM_DAYS,
            "input_dim": INPUT_DIM,
            "features": ["temp_max", "temp_min", "humidity", "wind_max", "precipitation", "fire_count"],
            "train_days": x_train.shape[0],
            "test_days": x_test.shape[0],
        },
        "results": results,
        "feature_stats": feature_stats,
    }
    
    json_path = RESULTS_DIR / "benchmark_results_real.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ JSON: {json_path}")
    
    # LaTeX
    latex_path = RESULTS_DIR / "tabela_real_data.tex"
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Model comparison on real wildfire data from Cear\'a (NASA FIRMS + INPE + Open-Meteo). 15 municipalities, 97 days of climate data, 377 fire detections.}")
    lines.append(r"\label{tab:real_data}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{@{}lccccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Model} & \textbf{RMSE}$\downarrow$ & \textbf{MAE}$\downarrow$ & \textbf{R\textsuperscript{2}}$\uparrow$ & \textbf{F1}$\uparrow$ & \textbf{Inf. (ms)} \\")
    lines.append(r"\midrule")
    best_rmse = min(r["rmse"] for r in results)
    best_r2 = max(r["r2"] for r in results)
    for r in results:
        rmse_s = f"\\textbf{{{r['rmse']:.4f}}}" if r["rmse"] == best_rmse else f"{r['rmse']:.4f}"
        r2_s = f"\\textbf{{{r['r2']:.4f}}}" if r["r2"] == best_r2 else f"{r['r2']:.4f}"
        lines.append(f"{r['model']} & {rmse_s} & {r['mae']:.4f} & {r2_s} & {r['f1_score']:.4f} & {r['inference_ms']:.1f} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    with open(latex_path, "w") as f:
        f.write("\n".join(lines))
    print(f"✅ LaTeX: {latex_path}")
    
    print("\n🎉 Experimento com dados reais concluído!")


if __name__ == "__main__":
    main()
