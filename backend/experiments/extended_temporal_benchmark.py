"""
EXP-ROBUST-003: Extended temporal benchmark (12-month dry season, INPE CSV).

Uses INPE BDQueimadas fields only (no Open-Meteo re-download) for 15 municipalities,
Jul/2024--Jun/2025 vs the original 97-day Mar--Jun/2026 subset.

Run:
  cd backend && ../.venv/bin/python -m experiments.extended_temporal_benchmark
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier

RESULTS_DIR = Path(__file__).parent / "results"
INPE_CSV = Path(__file__).resolve().parents[2] / "data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv"

MONITOR_MUN = [
    "FORTALEZA", "SOBRAL", "JUAZEIRO DO NORTE", "CRATO", "QUIXADÁ", "QUIXADA",
    "IGUATU", "CRATEÚS", "CRATEUS", "TIANGUÁ", "TIANGUA", "ICÓ", "ICO",
    "TAUÁ", "TAUA", "CANINDÉ", "CANINDE", "RUSSAS", "LIMoeiro do norte".upper(),
    "ITAPIPOCA",
]

def norm_mun(name: str) -> str:
    return name.strip().upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U").replace("Ã", "A").replace("Ç", "C")


def load_inpe_daily(csv_path: Path, start: str, end: str) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    """Returns dates, municipios, daily matrix (days x mun), auxiliary features."""
    start_d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")

    counts: dict[tuple[str, str], int] = defaultdict(int)
    drought: dict[tuple[str, str], list[float]] = defaultdict(list)
    risk: dict[tuple[str, str], list[float]] = defaultdict(list)

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_date = row.get("data_pas") or row.get("data_hora_gmt") or ""
            try:
                dt = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
            except ValueError:
                continue
            if dt < start_d or dt > end_d:
                continue
            mun = norm_mun(row.get("municipio", ""))
            if not mun:
                continue
            dkey = dt.strftime("%Y-%m-%d")
            counts[(dkey, mun)] += 1
            try:
                drought[(dkey, mun)].append(float(row.get("numero_dias_sem_chuva") or 0))
            except ValueError:
                pass
            try:
                risk[(dkey, mun)].append(float(row.get("risco_fogo") or 0))
            except ValueError:
                pass

    mun_totals: dict[str, int] = defaultdict(int)
    for (_, mun), c in counts.items():
        mun_totals[mun] += c
    top_mun = sorted(mun_totals, key=mun_totals.get, reverse=True)[:15]

    all_dates = sorted({d for d, _ in counts.keys()} | {d for d, m in counts if m in top_mun})
    if not all_dates:
        raise RuntimeError("No INPE records in date range")

    d_idx = {d: i for i, d in enumerate(all_dates)}
    m_idx = {m: i for i, m in enumerate(top_mun)}
    fire = np.zeros((len(all_dates), len(top_mun)))
    dry = np.zeros_like(fire)
    rsk = np.zeros_like(fire)

    for (dkey, mun), c in counts.items():
        if mun not in m_idx:
            continue
        i, j = d_idx[dkey], m_idx[mun]
        fire[i, j] = c
        dry[i, j] = np.mean(drought[(dkey, mun)]) if drought[(dkey, mun)] else 0
        rsk[i, j] = np.mean(risk[(dkey, mun)]) if risk[(dkey, mun)] else 0

    return all_dates, top_mun, fire, np.stack([dry, rsk], axis=-1)


def build_samples(fire: np.ndarray, aux: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows_x, rows_y = [], []
    num_days, num_mun = fire.shape
    for t in range(3, num_days - 1):
        for m in range(num_mun):
            hist = fire[t - 2 : t + 1, m]
            pers = float(hist.sum() / max(hist.max(), 1.0))
            fire_next = fire[t + 1, m]
            if fire_next > 0 and pers > 0.25:
                label = 2
            elif fire_next > 0 or (aux[t, m, 1] > 0.5 and fire[t, m] > 0):
                label = 1
            else:
                label = 0
            feat = np.concatenate([fire[t - 2 : t + 1, m], aux[t, m], [pers, fire[t, m]]])
            rows_x.append(feat)
            rows_y.append(label)
    return np.array(rows_x, dtype=np.float32), np.array(rows_y, dtype=np.int64)


def eval_yes_alert(y_true: np.ndarray, proba_yes: np.ndarray, thresh: float = 0.3) -> dict:
    pred = proba_yes >= thresh
    true = y_true == 2
    tp = int((pred & true).sum())
    fp = int((pred & ~true).sum())
    fn = int((~pred & true).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": prec, "recall": rec, "tp": tp, "fp": fp, "fn": fn}


def run_window(label: str, start: str, end: str) -> dict:
    dates, muns, fire, aux = load_inpe_daily(INPE_CSV, start, end)
    X, y = build_samples(fire, aux)
    n = len(y)
    tr, va = int(n * 0.7), int(n * 0.1)
    X_train, y_train = X[:tr], y[:tr]
    X_test, y_test = X[tr + va :], y[tr + va :]

    clf = XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.04,
        objective="multi:softprob", num_class=3, random_state=42,
    )
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_test)[:, 2]
    alert = eval_yes_alert(y_test, proba)

    mlp = MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=300, random_state=42)
    y_bin = (y_train == 2).astype(int)
    mlp.fit(X_train, y_bin)
    y_pred_bin = mlp.predict(X_test)
    y_test_bin = (y_test == 2).astype(int)

    return {
        "label": label,
        "start": start,
        "end": end,
        "num_days": len(dates),
        "num_municipalities": len(muns),
        "total_focos": int(fire.sum()),
        "samples": int(n),
        "test_samples": int(len(y_test)),
        "yes_in_test": int((y_test == 2).sum()),
        "xgb_yes_alert": alert,
        "xgb_macro_f1": float(f1_score(y_test, clf.predict(X_test), average="macro", zero_division=0)),
        "mlp_yes_f1": float(f1_score(y_test_bin, y_pred_bin, zero_division=0)),
        "mlp_yes_precision": float(precision_score(y_test_bin, y_pred_bin, zero_division=0)),
        "mlp_yes_recall": float(recall_score(y_test_bin, y_pred_bin, zero_division=0)),
    }


def write_latex(results: list[dict], path: Path) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Extended vs.\ short-window INPE benchmarks (XGBoost 3-class, YES alert at $P\geq 0.30$).}",
        r"\label{tab:extended-temporal}",
        r"\small",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        r"\textbf{Window} & \textbf{Days} & \textbf{Focos} & \textbf{Test $n$} & \textbf{Prec.} & \textbf{Recall} & \textbf{FP} \\",
        r"\midrule",
    ]
    for r in results:
        a = r["xgb_yes_alert"]
        prec = f"{a['precision']:.1%}".replace("%", "\\%")
        rec = f"{a['recall']:.1%}".replace("%", "\\%")
        lines.append(
            f"{r['label']} & {r['num_days']} & {r['total_focos']} & {r['test_samples']} & {prec} & {rec} & {a['fp']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print("EXP-ROBUST-003: Extended temporal benchmark")
    windows = [
        ("Short (Mar--Jun/2026 proxy)", "2025-03-01", "2025-06-30"),
        ("Dry season 2024", "2024-07-01", "2024-12-31"),
        ("Dry season 2025", "2025-07-01", "2025-12-31"),
        ("Full 12 mo (Jul/24--Jun/25)", "2024-07-01", "2025-06-30"),
    ]
    results = [run_window(*w) for w in windows]
    payload = {"experiment": "EXP-ROBUST-003", "windows": results}
    out_json = RESULTS_DIR / "EXP-ROBUST-003_extended.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_latex(results, RESULTS_DIR / "tabela_extended_temporal.tex")

    md = ["# EXP-ROBUST-003 — Extended Temporal Benchmark", ""]
    for r in results:
        a = r["xgb_yes_alert"]
        md.append(f"## {r['label']} ({r['start']} → {r['end']})")
        md.append(f"- Days: {r['num_days']}, Focos: {r['total_focos']}, Test n: {r['test_samples']}")
        md.append(f"- YES alert: precision={a['precision']:.1%}, recall={a['recall']:.1%}, FP={a['fp']}")
        md.append("")
    (RESULTS_DIR / "EXP-ROBUST-003_extended.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Saved {out_json.name}")


if __name__ == "__main__":
    main()
