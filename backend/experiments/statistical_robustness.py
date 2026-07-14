"""
Exp-B robustness: bootstrap 95% CI, multi-seed regression, paired model comparison.

PROVENANCE (important for reproducibility)
------------------------------------------
This script mixes two data sources, and their metrics must not be conflated:

1. PUBLISHED v9 contingency tables (``published_v9_bootstrap`` in the JSON):
   TP=23 / FP=5 (XGBoost YES) and TP=11 / FP=1 (NeKo YES) are taken verbatim
   from the Exp-B v9 run (TASK-083_FINAL.md), which used the full TASK-083
   feature pipeline. This script only performs a binomial bootstrap on those
   counts; it does NOT retrain that pipeline. These are the alert-precision
   CIs reported in the manuscript (82.1% CI [67.9%, 96.4%], etc.).

2. IN-SCRIPT simplified re-derivation (``yes_alert_point``,
   ``yes_alert_bootstrap``, ``paired_tests``): a compact XGBoost 3-class
   model retrained here on the archived 97-day / 15-municipality daily
   dataset (data/climate_ceara_90d.json + hotspot archives). Its YES
   operating point is much more conservative (typically 1 TP at P>=0.30)
   because the feature engineering and data volume differ from TASK-083 v9.
   It exists to support the paired significance tests (Wilcoxon/McNemar) and
   the multi-seed regression CIs, NOT to reproduce the published alert
   precision. A low TP here is expected and is not a discrepancy with the
   manuscript.

Outputs:
  results/EXP-ROBUST-001_bootstrap.json  (includes paired_tests)
  results/EXP-ROBUST-001_bootstrap.md
  results/tabela_bootstrap_ci.tex
  results/tabela_paired_tests.tex

Run:
  cd backend && python -m experiments.statistical_robustness
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import binom, wilcoxon
from sklearn.metrics import precision_recall_fscore_support
from sklearn.neural_network import MLPRegressor
from xgboost import XGBClassifier, XGBRegressor

RESULTS_DIR = Path(__file__).parent / "results"
DATA_DIR = Path(__file__).parent / "data"
N_BOOT = 2000
SEEDS = [42, 7, 123, 2024, 999]
YES_THRESH = 0.30


def load_real_data():
    with open(DATA_DIR / "climate_ceara_90d.json") as f:
        climate = json.load(f)
    firms_path = DATA_DIR / "firms_ceara_7d.json"
    focos_firms = json.load(open(firms_path)) if firms_path.exists() else []
    inpe_path = DATA_DIR / "inpe_ceara_historico.json"
    focos_inpe = json.load(open(inpe_path)) if inpe_path.exists() else []
    return climate, focos_firms, focos_inpe


def build_daily_dataset(climate, focos_firms, focos_inpe):
    from collections import defaultdict
    from scipy.spatial.distance import cdist

    municipios = list(climate.keys())
    num_mun = len(municipios)
    dates = climate[municipios[0]]["dates"]
    num_days = len(dates)
    coords = np.array([[climate[m]["lat"], climate[m]["lon"]] for m in municipios])
    focos_por_mun_dia = defaultdict(lambda: defaultdict(int))

    def closest_mun(lat, lon):
        dists = np.sqrt((coords[:, 0] - lat) ** 2 + (coords[:, 1] - lon) ** 2)
        return municipios[int(np.argmin(dists))]

    for f in focos_firms:
        try:
            lat, lon = float(f.get("latitude", 0)), float(f.get("longitude", 0))
            focos_por_mun_dia[closest_mun(lat, lon)][f.get("acq_date", "")] += 1
        except Exception:
            pass
    for f in focos_inpe:
        try:
            lat, lon = float(f.get("lat", 0)), float(f.get("lon", 0))
            date = f.get("date", "") or (f.get("data_hora_gmt", "")[:10] if f.get("data_hora_gmt") else "")
            focos_por_mun_dia[closest_mun(lat, lon)][date] += 1
        except Exception:
            pass

    x_data = np.zeros((num_days, num_mun, 6))
    raw_fire = np.zeros((num_days, num_mun))
    for i, mun in enumerate(municipios):
        c = climate[mun]
        for d, date_str in enumerate(dates):
            focos = focos_por_mun_dia[mun].get(date_str, 0)
            raw_fire[d, i] = focos
            x_data[d, i, 0] = c["temp_max"][d] if c["temp_max"][d] is not None else 30.0
            x_data[d, i, 1] = c["temp_min"][d] if c["temp_min"][d] is not None else 22.0
            x_data[d, i, 2] = c["humidity"][d] if c["humidity"][d] is not None else 60.0
            x_data[d, i, 3] = c["wind_max"][d] if c["wind_max"][d] is not None else 5.0
            x_data[d, i, 4] = c["precip"][d] if c["precip"][d] is not None else 0.0
            x_data[d, i, 5] = focos

    for f_idx in range(6):
        fmin, fmax = x_data[:, :, f_idx].min(), x_data[:, :, f_idx].max()
        if fmax > fmin:
            x_data[:, :, f_idx] = (x_data[:, :, f_idx] - fmin) / (fmax - fmin)

    dist_matrix = cdist(coords, coords)
    adj = np.zeros((num_mun, num_mun))
    for i in range(num_mun):
        for j in np.argsort(dist_matrix[i])[1:5]:
            adj[i, j] = adj[j, i] = 1
    return x_data, adj, municipios, dates, raw_fire


def temporal_split(x, train_ratio=0.7, val_ratio=0.1):
    n = x.shape[0]
    tr, va = int(n * train_ratio), int(n * (train_ratio + val_ratio))
    return {"train": x[:tr], "val": x[tr:va], "test": x[va:]}


def persistence_score(focos_hist: np.ndarray) -> float:
    """3-day weighted fire history for a municipality (0-1)."""
    if focos_hist.size == 0:
        return 0.0
    weights = np.array([1.0, 0.5, 0.25][: len(focos_hist)])
    return float(min(1.0, (focos_hist * weights).sum() / max(weights.sum(), 1e-6)))


def build_3class_samples(x_data: np.ndarray, raw_fire: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build features and labels aligned with Exp-B v8/v9 definitions."""
    num_days, num_mun, _ = x_data.shape
    rows_x, rows_y = [], []
    for t in range(3, num_days - 1):
        for m in range(num_mun):
            hist = raw_fire[t - 2 : t + 1, m]
            pers = persistence_score(hist / max(hist.max(), 1.0))
            fire_next = raw_fire[t + 1, m]
            fire_today = raw_fire[t, m]

            temp = x_data[t, m, 0]
            hum = x_data[t, m, 2]
            wind = x_data[t, m, 3]
            precip = x_data[t, m, 4]
            climate_risk = float(temp * 0.3 + (1 - hum) * 0.3 + wind * 0.2 + (1 - min(precip * 5, 1)) * 0.2)

            if fire_next > 0 and pers > 0.3:
                label = 2  # YES
            elif fire_next > 0 or (climate_risk > 0.55 and fire_today > 0):
                label = 1  # UNCERTAIN
            else:
                label = 0  # NO

            feat = np.concatenate([
                x_data[t, m], x_data[t - 1, m], x_data[t - 2, m],
                [pers, climate_risk, x_data[t, m, 5]],
            ])
            rows_x.append(feat)
            rows_y.append(label)

    return np.array(rows_x, dtype=np.float32), np.array(rows_y, dtype=np.int64)


def yes_alert_metrics(y_true: np.ndarray, proba_yes: np.ndarray, thresh: float = YES_THRESH) -> dict:
    """Operational YES alert: precision/recall on fire-next-day (label YES=2)."""
    pred_yes = proba_yes >= thresh
    true_yes = y_true == 2
    tp = int((pred_yes & true_yes).sum())
    fp = int((pred_yes & ~true_yes).sum())
    fn = int((~pred_yes & true_yes).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def bootstrap_ci(values: np.ndarray, alpha: float = 0.05) -> tuple[float, float, float]:
    lo = float(np.percentile(values, 100 * alpha / 2))
    hi = float(np.percentile(values, 100 * (1 - alpha / 2)))
    return float(np.mean(values)), lo, hi


def bootstrap_yes_metrics(y_true: np.ndarray, proba: np.ndarray, n: int = N_BOOT) -> dict:
    rng = np.random.default_rng(42)
    n_samples = len(y_true)
    precs, recs, f1s = [], [], []
    for _ in range(n):
        idx = rng.integers(0, n_samples, size=n_samples)
        m = yes_alert_metrics(y_true[idx], proba[idx])
        precs.append(m["precision"])
        recs.append(m["recall"])
        f1s.append(m["f1"])
    out = {}
    for name, arr in [("precision", precs), ("recall", recs), ("f1", f1s)]:
        a = np.array(arr)
        mean, lo, hi = bootstrap_ci(a)
        out[name] = {"mean": mean, "ci95_lo": lo, "ci95_hi": hi}
    return out


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_true - y_pred
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    y_bin = (y_true[:, -1] > 0.05).astype(int) if y_true.ndim > 1 else (y_true > 0.05).astype(int)
    p_bin = (y_pred[:, -1] > 0.05).astype(int) if y_pred.ndim > 1 else (y_pred > 0.05).astype(int)
    tp = int(((y_bin == 1) & (p_bin == 1)).sum())
    fp = int(((y_bin == 0) & (p_bin == 1)).sum())
    fn = int(((y_bin == 1) & (p_bin == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"rmse": rmse, "mae": mae, "r2": r2, "f1_score": f1}


PERS_FEAT_IDX = 18
FIRE_TODAY_FEAT_IDX = 20


def persistence_3class_predict(X: np.ndarray) -> np.ndarray:
    """NeKo-style persistence-only 3-class baseline (no climate features)."""
    pers = X[:, PERS_FEAT_IDX]
    fire_today = X[:, FIRE_TODAY_FEAT_IDX]
    fire_signal = fire_today > 0.01
    preds = np.zeros(len(X), dtype=np.int64)
    preds[(pers > 0.3) & fire_signal] = 2
    preds[(preds == 0) & (fire_signal | (pers > 0.25))] = 1
    return preds


def mcnemar_exact(b: int, c: int) -> dict:
    """Two-sided exact McNemar test from discordant counts (b=A wrong B right, c=A right B wrong)."""
    n = b + c
    if n == 0:
        return {"discordant": 0, "b": b, "c": c, "p_value": 1.0, "statistic": 0.0}
    k = min(b, c)
    p_one = float(binom.cdf(k, n, 0.5))
    p_two = min(1.0, 2.0 * p_one)
    return {
        "discordant": n,
        "b": int(b),
        "c": int(c),
        "p_value": p_two,
        "statistic": float(abs(b - c)),
    }


def run_paired_tests(
    mlp_ms: dict,
    xgb_ms: dict,
    y_test: np.ndarray,
    y_pred_xgb: np.ndarray,
    X_test: np.ndarray,
    proba_yes: np.ndarray,
) -> dict:
    """Wilcoxon (per-seed RMSE) and McNemar (3-class vs persistence baseline)."""
    mlp_rmses = np.array([m["rmse"] for m in mlp_ms["per_seed"]], dtype=np.float64)
    xgb_rmses = np.array([m["rmse"] for m in xgb_ms["per_seed"]], dtype=np.float64)
    try:
        w_stat, w_p = wilcoxon(mlp_rmses, xgb_rmses, alternative="two-sided")
    except ValueError:
        w_stat, w_p = 0.0, 1.0

    y_pred_pers = persistence_3class_predict(X_test)
    correct_xgb = y_pred_xgb == y_test
    correct_pers = y_pred_pers == y_test
    mcnemar_3class = mcnemar_exact(
        int((~correct_xgb & correct_pers).sum()),
        int((correct_xgb & ~correct_pers).sum()),
    )

    xgb_yes = proba_yes >= YES_THRESH
    pers_yes = y_pred_pers == 2
    true_yes = y_test == 2
    xgb_yes_ok = xgb_yes == true_yes
    pers_yes_ok = pers_yes == true_yes
    mcnemar_yes = mcnemar_exact(
        int((~xgb_yes_ok & pers_yes_ok).sum()),
        int((xgb_yes_ok & ~pers_yes_ok).sum()),
    )

    return {
        "wilcoxon_rmse_mlp_vs_xgb": {
            "comparison": "MLP vs XGBoost regressor (per-seed RMSE, n=5)",
            "mlp_rmse_per_seed": mlp_rmses.tolist(),
            "xgb_rmse_per_seed": xgb_rmses.tolist(),
            "mean_diff_mlp_minus_xgb": float((mlp_rmses - xgb_rmses).mean()),
            "statistic": float(w_stat),
            "p_value": float(w_p),
            "significant_005": bool(w_p < 0.05),
        },
        "mcnemar_3class_xgb_vs_persistence": {
            "comparison": "XGBoost 3-class vs NeKo-style persistence-only baseline",
            "xgb_accuracy": float(correct_xgb.mean()),
            "persistence_accuracy": float(correct_pers.mean()),
            **mcnemar_3class,
            "significant_005": bool(mcnemar_3class["p_value"] < 0.05),
        },
        "mcnemar_yes_alert_xgb_vs_persistence": {
            "comparison": f"YES alert (XGB P>={YES_THRESH}) vs persistence YES (class 2)",
            "xgb_yes_precision": float(yes_alert_metrics(y_test, proba_yes)["precision"]),
            "persistence_yes_precision": float(
                yes_alert_metrics(y_test, pers_yes.astype(np.float64))["precision"]
            ),
            **mcnemar_yes,
            "significant_005": bool(mcnemar_yes["p_value"] < 0.05),
        },
    }


def run_multiseed_xgb_regression(x_data: np.ndarray, seeds: list[int]) -> dict:
    """Multi-seed XGBoost regressor on flattened next-step prediction task."""
    splits = temporal_split(x_data)
    x_train, x_test = splits["train"], splits["test"]
    input_dim = x_data.shape[2]
    metrics_by_seed = []

    x_tr_flat = x_train[:-1].reshape(-1, input_dim)
    y_tr_flat = x_train[1:].reshape(-1, input_dim)
    x_te_flat = x_test[:-1].reshape(-1, input_dim)
    y_te_flat = x_test[1:].reshape(-1, input_dim)

    for seed in seeds:
        xgb = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            random_state=seed,
            n_jobs=-1,
            verbosity=0,
        )
        xgb.fit(x_tr_flat, y_tr_flat)
        y_pred = xgb.predict(x_te_flat)
        metrics_by_seed.append(regression_metrics(y_te_flat, y_pred))

    rmses = np.array([m["rmse"] for m in metrics_by_seed])
    f1s = np.array([m["f1_score"] for m in metrics_by_seed])
    r2s = np.array([m["r2"] for m in metrics_by_seed])
    return {
        "seeds": seeds,
        "rmse": {"mean": float(rmses.mean()), "std": float(rmses.std()), **dict(zip(
            ["ci95_lo", "ci95_hi"],
            [float(np.percentile(rmses, 2.5)), float(np.percentile(rmses, 97.5))],
        ))},
        "r2": {"mean": float(r2s.mean()), "std": float(r2s.std()), **dict(zip(
            ["ci95_lo", "ci95_hi"],
            [float(np.percentile(r2s, 2.5)), float(np.percentile(r2s, 97.5))],
        ))},
        "f1": {"mean": float(f1s.mean()), "std": float(f1s.std())},
        "per_seed": metrics_by_seed,
    }


def run_multiseed_regression(x_data: np.ndarray, seeds: list[int]) -> dict:
    splits = temporal_split(x_data)
    x_train, x_test = splits["train"], splits["test"]
    input_dim = x_data.shape[2]
    metrics_by_seed = []

    x_tr_flat = x_train[:-1].reshape(-1, input_dim)
    y_tr_flat = x_train[1:].reshape(-1, input_dim)
    x_te_flat = x_test[:-1].reshape(-1, input_dim)
    y_te_flat = x_test[1:].reshape(-1, input_dim)

    for seed in seeds:
        mlp = MLPRegressor(
            hidden_layer_sizes=(256, 128),
            max_iter=200,
            random_state=seed,
            early_stopping=True,
            validation_fraction=0.1,
        )
        mlp.fit(x_tr_flat, y_tr_flat)
        y_pred = mlp.predict(x_te_flat)
        metrics_by_seed.append(regression_metrics(y_te_flat, y_pred))

    rmses = np.array([m["rmse"] for m in metrics_by_seed])
    f1s = np.array([m["f1_score"] for m in metrics_by_seed])
    r2s = np.array([m["r2"] for m in metrics_by_seed])
    return {
        "seeds": seeds,
        "rmse": {"mean": float(rmses.mean()), "std": float(rmses.std()), **dict(zip(
            ["ci95_lo", "ci95_hi"],
            [float(np.percentile(rmses, 2.5)), float(np.percentile(rmses, 97.5))],
        ))},
        "r2": {"mean": float(r2s.mean()), "std": float(r2s.std()), **dict(zip(
            ["ci95_lo", "ci95_hi"],
            [float(np.percentile(r2s, 2.5)), float(np.percentile(r2s, 97.5))],
        ))},
        "f1": {"mean": float(f1s.mean()), "std": float(f1s.std())},
        "per_seed": metrics_by_seed,
    }


def bootstrap_published_v9(n: int = N_BOOT) -> dict:
    """Non-parametric bootstrap on published TP/FP counts (Exp-B v9, TASK-083_FINAL)."""
    rng = np.random.default_rng(42)

    def prec_ci(tp: int, fp: int) -> dict:
        alerts = np.array([1] * tp + [0] * fp)
        precs = []
        for _ in range(n):
            idx = rng.integers(0, len(alerts), len(alerts))
            s = alerts[idx]
            precs.append(s.mean() if len(s) else 0.0)
        a = np.array(precs)
        return {
            "point": tp / (tp + fp) if tp + fp else 0.0,
            "ci95_lo": float(np.percentile(a, 2.5)),
            "ci95_hi": float(np.percentile(a, 97.5)),
        }

    # XGBoost P(YES)>=0.3: TP=23, FP=5; NeKo YES: TP=11, FP=1
    xgb = prec_ci(23, 5)
    neko = prec_ci(11, 1)
    # Combined coverage 88% on 377 focos → bootstrap hits/misses
    hits = int(round(0.88 * 377))
    misses = 377 - hits
    cov_samples = []
    flags = np.array([1] * hits + [0] * misses)
    for _ in range(n):
        idx = rng.integers(0, len(flags), len(flags))
        cov_samples.append(flags[idx].mean())
    cov_a = np.array(cov_samples)
    return {
        "xgb_precision": xgb,
        "neko_precision": neko,
        "coverage": {
            "point": 0.88,
            "ci95_lo": float(np.percentile(cov_a, 2.5)),
            "ci95_hi": float(np.percentile(cov_a, 97.5)),
        },
    }


def pct_tex(v: float) -> str:
    return f"{v:.1%}".replace("%", "\\%")


def write_latex_table_v9(pub: dict, path: Path) -> None:
    x, n = pub["xgb_precision"], pub["neko_precision"]
    c = pub["coverage"]
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Bootstrap 95\% CI for published Exp-B v9 alert metrics (2{,}000 resamples on contingency tables).}",
        r"\label{tab:bootstrap-v9}",
        r"\small",
        r"\begin{tabular}{@{}lccc@{}}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Point} & \textbf{CI low} & \textbf{CI high} \\",
        r"\midrule",
        f"XGBoost YES precision (23 TP, 5 FP) & {pct_tex(x['point'])} & {pct_tex(x['ci95_lo'])} & {pct_tex(x['ci95_hi'])} \\\\",
        f"NeKo-PIGNN YES precision (11 TP, 1 FP) & {pct_tex(n['point'])} & {pct_tex(n['ci95_lo'])} & {pct_tex(n['ci95_hi'])} \\\\",
        f"Combined coverage (YES+UNCERTAIN) & {pct_tex(c['point'])} & {pct_tex(c['ci95_lo'])} & {pct_tex(c['ci95_hi'])} \\\\",
        r"\midrule",
        r"MLP RMSE (5 seeds, reproduced) & --- & see Table~\ref{tab:bootstrap-ci} & --- \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_table(boot: dict, mlp_ms: dict, path: Path) -> None:
    p = boot["yes_alert_bootstrap"]
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Bootstrap 95\% confidence intervals (2{,}000 resamples, test holdout).}",
        r"\label{tab:bootstrap-ci}",
        r"\small",
        r"\begin{tabular}{@{}lccc@{}}",
        r"\toprule",
        r"\textbf{Metric (YES alerts, $P\geq 0.30$)} & \textbf{Point} & \textbf{CI 95\% low} & \textbf{CI 95\% high} \\",
        r"\midrule",
        f"Precision & {pct_tex(p['precision']['mean'])} & {pct_tex(p['precision']['ci95_lo'])} & {pct_tex(p['precision']['ci95_hi'])} \\\\",
        f"Recall & {pct_tex(p['recall']['mean'])} & {pct_tex(p['recall']['ci95_lo'])} & {pct_tex(p['recall']['ci95_hi'])} \\\\",
        f"F1 & {p['f1']['mean']:.3f} & {p['f1']['ci95_lo']:.3f} & {p['f1']['ci95_hi']:.3f} \\\\",
        r"\midrule",
        f"MLP RMSE (5 seeds) & {mlp_ms['rmse']['mean']:.4f} & {mlp_ms['rmse']['ci95_lo']:.4f} & {mlp_ms['rmse']['ci95_hi']:.4f} \\\\",
        f"MLP R$^2$ (5 seeds) & {mlp_ms['r2']['mean']:.3f} & {mlp_ms['r2']['ci95_lo']:.3f} & {mlp_ms['r2']['ci95_hi']:.3f} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_paired_tests(paired: dict, path: Path) -> None:
    w = paired["wilcoxon_rmse_mlp_vs_xgb"]
    m3 = paired["mcnemar_3class_xgb_vs_persistence"]
    my = paired["mcnemar_yes_alert_xgb_vs_persistence"]

    def p_fmt(p: float) -> str:
        if p < 0.001:
            return "$<0.001$"
        return f"{p:.4f}"

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Paired significance tests: Wilcoxon signed-rank (regression RMSE) and exact McNemar (classification).}",
        r"\label{tab:paired-tests}",
        r"\small",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"\textbf{Test} & \textbf{Statistic} & \textbf{$p$-value} & \textbf{Sig.\ @0.05} & \textbf{Notes} \\",
        r"\midrule",
        f"Wilcoxon: MLP vs XGB RMSE & {w['statistic']:.2f} & {p_fmt(w['p_value'])} & "
        f"{'Yes' if w['significant_005'] else 'No'} & "
        f"mean $\\Delta$={w['mean_diff_mlp_minus_xgb']:.4f} \\\\",
        f"McNemar: 3-class XGB vs persistence & {m3['statistic']:.0f} & {p_fmt(m3['p_value'])} & "
        f"{'Yes' if m3['significant_005'] else 'No'} & "
        f"acc {m3['xgb_accuracy']:.1%} vs {m3['persistence_accuracy']:.1%} \\\\",
        f"McNemar: YES alert XGB vs persistence & {my['statistic']:.0f} & {p_fmt(my['p_value'])} & "
        f"{'Yes' if my['significant_005'] else 'No'} & "
        f"prec {my['xgb_yes_precision']:.1%} vs {my['persistence_yes_precision']:.1%} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    t0 = time.time()
    print("=" * 72)
    print("EXP-ROBUST-001: Statistical robustness (bootstrap CI + multi-seed)")
    print("=" * 72)

    climate, firms, inpe = load_real_data()
    x_data, adj, municipios, dates, raw_fire = build_daily_dataset(climate, firms, inpe)
    splits = temporal_split(x_data)

    X, y = build_3class_samples(x_data, raw_fire)
    num_days = x_data.shape[0]
    train_end = splits["train"].shape[0]
    val_end = train_end + splits["val"].shape[0]

    # Align sample indices to temporal split (approximate by day fraction)
    n = len(y)
    train_n = int(n * 0.70)
    val_n = int(n * 0.10)
    X_train, y_train = X[:train_n], y[:train_n]
    X_val, y_val = X[train_n : train_n + val_n], y[train_n : train_n + val_n]
    X_test, y_test = X[train_n + val_n :], y[train_n + val_n :]

    print(f"  3-class samples: {len(y)} (train={len(y_train)}, val={len(y_val)}, test={len(y_test)})")
    print(f"  Class balance test: NO={int((y_test==0).sum())}, UNC={int((y_test==1).sum())}, YES={int((y_test==2).sum())}")

    clf = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=3,
        random_state=42,
        eval_metric="mlogloss",
    )
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_test)
    proba_yes = proba[:, 2]

    point = yes_alert_metrics(y_test, proba_yes)
    boot = bootstrap_yes_metrics(y_test, proba_yes)
    y_pred = clf.predict(X_test)
    macro = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0, labels=[0, 1, 2]
    )

    print(f"\n  YES alert @ P>={YES_THRESH}: precision={point['precision']:.1%} recall={point['recall']:.1%}")
    print(f"  Bootstrap precision CI: [{boot['precision']['ci95_lo']:.1%}, {boot['precision']['ci95_hi']:.1%}]")

    print("\n  Multi-seed MLP regression (5 seeds)...")
    mlp_ms = run_multiseed_regression(x_data, SEEDS)

    print("  Multi-seed XGBoost regression (5 seeds)...")
    xgb_ms = run_multiseed_xgb_regression(x_data, SEEDS)

    print("  Paired tests (Wilcoxon RMSE + McNemar 3-class)...")
    paired = run_paired_tests(mlp_ms, xgb_ms, y_test, y_pred, X_test, proba_yes)
    w = paired["wilcoxon_rmse_mlp_vs_xgb"]
    m3 = paired["mcnemar_3class_xgb_vs_persistence"]
    print(f"    Wilcoxon RMSE: p={w['p_value']:.4f} (MLP mean={mlp_ms['rmse']['mean']:.4f}, XGB={xgb_ms['rmse']['mean']:.4f})")
    print(f"    McNemar 3-class: p={m3['p_value']:.4f} (acc {m3['xgb_accuracy']:.1%} vs {m3['persistence_accuracy']:.1%})")

    payload = {
        "experiment": "EXP-ROBUST-001",
        "provenance_note": (
            "'published_v9_bootstrap' resamples the published TASK-083 v9 "
            "contingency tables (TP=23/FP=5, TP=11/FP=1) and is the source of "
            "the manuscript alert-precision CIs. 'yes_alert_point' and "
            "'paired_tests' come from a simplified in-script re-derivation on "
            "the archived 97-day dataset; its low YES TP count is expected and "
            "does not reproduce (nor contradict) the published v9 pipeline."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "n_bootstrap": N_BOOT,
            "yes_threshold": YES_THRESH,
            "seeds_regression": SEEDS,
            "num_days": num_days,
            "num_municipalities": len(municipios),
            "test_samples_3class": int(len(y_test)),
        },
        "yes_alert_point": point,
        "yes_alert_bootstrap": boot,
        "macro_f1_test": float(macro[2]),
        "mlp_multiseed_regression": mlp_ms,
        "xgb_multiseed_regression": xgb_ms,
        "paired_tests": paired,
        "runtime_sec": round(time.time() - t0, 2),
    }

    json_path = RESULTS_DIR / "EXP-ROBUST-001_bootstrap.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# EXP-ROBUST-001 — Bootstrap CI & Multi-Seed Regression",
        "",
        f"**Date:** {payload['timestamp']}",
        f"**Runtime:** {payload['runtime_sec']}s",
        "",
        "> **Provenance:** the manuscript alert-precision CIs come from the",
        "> *published v9* section below (binomial bootstrap on TASK-083_FINAL",
        "> contingency tables, TP=23/FP=5). The YES-alert table immediately",
        "> below uses a simplified in-script re-derivation (97-day archived",
        "> dataset) that supports the paired tests only; its low TP count is",
        "> expected and is not comparable to the published v9 pipeline.",
        "",
        "## YES-class alert metrics (simplified in-script model, P≥0.30)",
        "",
        "| Metric | Point | Bootstrap 95% CI |",
        "|--------|-------|------------------|",
        f"| Precision | {point['precision']:.1%} | [{boot['precision']['ci95_lo']:.1%}, {boot['precision']['ci95_hi']:.1%}] |",
        f"| Recall | {point['recall']:.1%} | [{boot['recall']['ci95_lo']:.1%}, {boot['recall']['ci95_hi']:.1%}] |",
        f"| F1 | {point['f1']:.3f} | [{boot['f1']['ci95_lo']:.3f}, {boot['f1']['ci95_hi']:.3f}] |",
        f"| TP / FP / FN | {point['tp']} / {point['fp']} / {point['fn']} | — |",
        "",
        "## MLP regression (5 seeds, temporal split)",
        "",
        f"- RMSE: {mlp_ms['rmse']['mean']:.4f} ± {mlp_ms['rmse']['std']:.4f} (95% CI [{mlp_ms['rmse']['ci95_lo']:.4f}, {mlp_ms['rmse']['ci95_hi']:.4f}])",
        f"- R²: {mlp_ms['r2']['mean']:.3f} (95% CI [{mlp_ms['r2']['ci95_lo']:.3f}, {mlp_ms['r2']['ci95_hi']:.3f}])",
        "",
        "## XGBoost regression (5 seeds, temporal split)",
        "",
        f"- RMSE: {xgb_ms['rmse']['mean']:.4f} ± {xgb_ms['rmse']['std']:.4f}",
        f"- R²: {xgb_ms['r2']['mean']:.3f}",
        "",
        "## Paired significance tests",
        "",
        f"- Wilcoxon RMSE (MLP vs XGB): p={w['p_value']:.4f}, Δmean={w['mean_diff_mlp_minus_xgb']:.4f}",
        f"- McNemar 3-class (XGB vs persistence): p={m3['p_value']:.4f}",
        f"- McNemar YES alert: p={paired['mcnemar_yes_alert_xgb_vs_persistence']['p_value']:.4f}",
        "",
        "## Reproduce",
        "```bash",
        "cd backend && python -m experiments.statistical_robustness",
        "```",
    ]
    md_path = RESULTS_DIR / "EXP-ROBUST-001_bootstrap.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    tex_path = RESULTS_DIR / "tabela_bootstrap_ci.tex"
    write_latex_table(payload, mlp_ms, tex_path)

    # Bootstrap on published Exp-B v9 contingency tables (TASK-083_FINAL)
    pub = bootstrap_published_v9()
    payload["published_v9_bootstrap"] = pub
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_lines.extend([
        "",
        "## Published v9 alert metrics (binomial bootstrap, TP/FP from TASK-083_FINAL)",
        "",
        f"| Metric | Point | 95% CI |",
        f"|--------|-------|--------|",
        f"| XGBoost YES precision | {pub['xgb_precision']['point']:.1%} | [{pub['xgb_precision']['ci95_lo']:.1%}, {pub['xgb_precision']['ci95_hi']:.1%}] |",
        f"| NeKo YES precision | {pub['neko_precision']['point']:.1%} | [{pub['neko_precision']['ci95_lo']:.1%}, {pub['neko_precision']['ci95_hi']:.1%}] |",
        f"| Combined coverage | {pub['coverage']['point']:.1%} | [{pub['coverage']['ci95_lo']:.1%}, {pub['coverage']['ci95_hi']:.1%}] |",
    ])
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    write_latex_table_v9(pub, RESULTS_DIR / "tabela_bootstrap_v9.tex")

    paired_tex = RESULTS_DIR / "tabela_paired_tests.tex"
    write_latex_paired_tests(paired, paired_tex)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n  Saved: {json_path.name}, {md_path.name}, {tex_path.name}, tabela_bootstrap_v9.tex, {paired_tex.name}")
    print("=" * 72)


if __name__ == "__main__":
    main()
