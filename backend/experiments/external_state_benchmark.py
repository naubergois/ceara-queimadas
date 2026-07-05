"""
EXP-ROBUST-005: External-state benchmark (MA, PI vs CE dry season 2025).

Downloads INPE monthly Brazil CSVs (Jul--Dec/2025), filters Maranhão and Piauí,
trains XGBoost 3-class on top-15 municipalities per state, evaluates YES alert @0.30.

Run:
  cd backend && ../.venv/bin/python -m experiments.external_state_benchmark
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

from experiments.extended_temporal_benchmark import (
    build_samples,
    eval_yes_alert,
    norm_mun,
)

RESULTS_DIR = Path(__file__).parent / "results"
CACHE_DIR = Path(__file__).parent / "data" / "inpe_monthly_br"
REPO_ROOT = Path(__file__).resolve().parents[2]
CE_CSV = REPO_ROOT / "data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv"
FIGURES_DIR = REPO_ROOT / "figures"

MONTHLY_URL = (
    "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/"
    "focos_mensal_br_{yyyymm}.csv"
)
DRY_MONTHS = ["202507", "202508", "202509", "202510", "202511", "202512"]
START = "2025-07-01"
END = "2025-12-31"

STATE_CONFIG = {
    "CE": {"label": "Ceará", "estados": {"CEARÁ"}, "estado_ids": {23}, "source": "local"},
    "MA": {"label": "Maranhão", "estados": {"MARANHÃO"}, "estado_ids": {21}, "source": "download"},
    "PI": {"label": "Piauí", "estados": {"PIAUÍ"}, "estado_ids": {22}, "source": "download"},
}


def norm_estado(name: str) -> str:
    return name.strip().upper()


def download_monthly_csv(yyyymm: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"focos_mensal_br_{yyyymm}.csv"
    if path.is_file() and path.stat().st_size > 0:
        return path
    url = MONTHLY_URL.format(yyyymm=yyyymm)
    resp = requests.get(url, timeout=120, headers={"User-Agent": "ceara-queimadas/exp-robust-005"})
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def prepare_state_csv(state_code: str) -> Path:
    """Filter monthly Brazil CSVs to a state-specific cache file."""
    cfg = STATE_CONFIG[state_code]
    out = CACHE_DIR / f"focos_{state_code.lower()}_dry_2025.csv"
    if out.is_file() and out.stat().st_size > 0:
        return out

    monthly_files = [download_monthly_csv(m) for m in DRY_MONTHS]
    write_header = True
    out.unlink(missing_ok=True)
    estado_names = {norm_estado(e) for e in cfg["estados"]}

    for mf in monthly_files:
        for chunk in pd.read_csv(mf, chunksize=250_000, low_memory=False):
            estado_col = chunk["estado"].astype(str).map(norm_estado)
            mask = estado_col.isin(estado_names)
            if "estado_id" in chunk.columns:
                eid = pd.to_numeric(chunk["estado_id"], errors="coerce")
                mask = mask | eid.isin(list(cfg["estado_ids"]))
            sub = chunk.loc[mask]
            if sub.empty:
                continue
            sub.to_csv(out, mode="a", header=write_header, index=False)
            write_header = False

    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"No INPE records for {state_code} in {START}..{END}")
    return out


def state_csv_paths(state_code: str) -> list[Path]:
    cfg = STATE_CONFIG[state_code]
    if cfg["source"] == "local":
        return [CE_CSV]
    return [prepare_state_csv(state_code)]


def load_inpe_daily(
    csv_paths: list[Path],
    start: str,
    end: str,
) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    """Aggregate daily focos for top-15 municipalities in date range."""
    start_d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")

    counts: dict[tuple[str, str], int] = defaultdict(int)
    drought: dict[tuple[str, str], list[float]] = defaultdict(list)
    risk: dict[tuple[str, str], list[float]] = defaultdict(list)

    for csv_path in csv_paths:
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
    if not top_mun:
        raise RuntimeError(f"No municipalities found in {start}..{end}")

    all_dates = sorted({d for d, _ in counts.keys()} | {d for d, m in counts if m in top_mun})
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


def run_state_benchmark(state_code: str) -> dict:
    cfg = STATE_CONFIG[state_code]
    csv_paths = state_csv_paths(state_code)

    dates, muns, fire, aux = load_inpe_daily(csv_paths, START, END)
    X, y = build_samples(fire, aux)
    n = len(y)
    tr, va = int(n * 0.7), int(n * 0.1)
    X_train, y_train = X[:tr], y[:tr]
    X_test, y_test = X[tr + va :], y[tr + va :]

    clf = XGBClassifier(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.04,
        objective="multi:softprob",
        num_class=3,
        random_state=42,
    )
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_test)[:, 2]
    alert = eval_yes_alert(y_test, proba, thresh=0.3)

    return {
        "state": state_code,
        "label": cfg["label"],
        "start": START,
        "end": END,
        "num_days": len(dates),
        "num_municipalities": len(muns),
        "municipalities": muns,
        "total_focos": int(fire.sum()),
        "samples": int(n),
        "test_samples": int(len(y_test)),
        "yes_in_test": int((y_test == 2).sum()),
        "xgb_yes_alert": alert,
        "xgb_macro_f1": float(
            f1_score(y_test, clf.predict(X_test), average="macro", zero_division=0)
        ),
    }


def write_latex(results: list[dict], path: Path) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{External-state validation: XGBoost 3-class YES alert at $P\geq 0.30$ (dry season Jul--Dec/2025).}",
        r"\label{tab:external-states}",
        r"\small",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"\textbf{State} & \textbf{Days} & \textbf{Hotspots} & \textbf{Precision} & \textbf{Recall} \\",
        r"\midrule",
    ]
    for r in results:
        a = r["xgb_yes_alert"]
        prec = f"{a['precision']:.1%}".replace("%", "\\%")
        rec = f"{a['recall']:.1%}".replace("%", "\\%")
        lines.append(
            f"{r['label']} & {r['num_days']} & {r['total_focos']} & {prec} & {rec} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(results: list[dict], path: Path) -> None:
    md = [
        "# EXP-ROBUST-005 — External State Benchmark",
        "",
        f"Window: {START} → {END} (dry season 2025)",
        "",
    ]
    for r in results:
        a = r["xgb_yes_alert"]
        md.append(f"## {r['label']} ({r['state']})")
        md.append(f"- Days: {r['num_days']}, Hotspots: {r['total_focos']}, Test n: {r['test_samples']}")
        md.append(
            f"- YES alert @0.30: precision={a['precision']:.1%}, recall={a['recall']:.1%}, "
            f"TP={a['tp']}, FP={a['fp']}, FN={a['fn']}"
        )
        md.append(f"- Macro F1: {r['xgb_macro_f1']:.3f}")
        md.append("")
    path.write_text("\n".join(md), encoding="utf-8")


def write_figure(results: list[dict], path: Path) -> None:
    states = [r["state"] for r in results]
    labels = [r["label"] for r in results]
    prec = [r["xgb_yes_alert"]["precision"] for r in results]
    rec = [r["xgb_yes_alert"]["recall"] for r in results]

    x = np.arange(len(states))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - width / 2, prec, width, label="Precision", color="#2B5F8A")
    ax.bar(x + width / 2, rec, width, label="Recall", color="#B15533")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("YES alert @0.30 — CE vs MA vs PI (dry 2025)")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    for i, (p, r_) in enumerate(zip(prec, rec)):
        ax.text(i - width / 2, p + 0.02, f"{p:.0%}", ha="center", fontsize=9)
        ax.text(i + width / 2, r_ + 0.02, f"{r_:.0%}", ha="center", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    print("EXP-ROBUST-005: External state benchmark (MA, PI vs CE)")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for code in ("CE", "MA", "PI"):
        print(f"  Running {code}...", flush=True)
        results.append(run_state_benchmark(code))

    payload = {
        "experiment": "EXP-ROBUST-005",
        "window": {"start": START, "end": END},
        "states": results,
    }
    out_json = RESULTS_DIR / "EXP-ROBUST-005_external_states.json"
    out_md = RESULTS_DIR / "EXP-ROBUST-005_external_states.md"
    out_tex = RESULTS_DIR / "tabela_external_states.tex"
    out_fig = FIGURES_DIR / "mapa-external-states.png"

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(results, out_md)
    write_latex(results, out_tex)
    write_figure(results, out_fig)

    print(f"Saved {out_json}")
    print(f"Saved {out_md}")
    print(f"Saved {out_tex}")
    print(f"Saved {out_fig}")
    for r in results:
        a = r["xgb_yes_alert"]
        print(
            f"  {r['state']}: days={r['num_days']} hotspots={r['total_focos']} "
            f"prec={a['precision']:.1%} rec={a['recall']:.1%}"
        )


if __name__ == "__main__":
    main()
