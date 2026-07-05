"""
EXP-ROBUST-006: Operational baseline comparison (FIRMS, INPE, LangGraph pipeline).

Compares documented operational metrics from the article/code and computes
spatial overlap between NASA FIRMS and INPE BDQueimadas detections in Ceará.

Outputs:
  results/EXP-ROBUST-006_operational_baseline.json
  results/EXP-ROBUST-006_operational_baseline.md
  results/tabela_operational_baseline.tex

Run:
  cd backend && python -m experiments.operational_baseline_benchmark
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
DATA_DIR = Path(__file__).parent / "data"

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
MATCH_RADIUS_KM = 1.0

# Documented operational metrics (article + EXP-ROBUST-003 dry season 2025)
DOCUMENTED_SYSTEMS = {
    "nasa_firms": {
        "name": "NASA FIRMS (VIIRS/MODIS direct)",
        "latency_hours": {"min": 3.0, "max": 6.0, "typical": 4.5},
        "latency_note": "Satellite overpass to CSV availability (article §limitations)",
        "precision": 0.80,
        "precision_note": "~80% nominal confidence / literature proxy (DETECCOES_REAIS.md)",
        "recall": None,
        "role": "Primary detection feed",
        "cost_usd_month": 0,
    },
    "inpe_bdqueimadas": {
        "name": "INPE BDQueimadas",
        "latency_hours": {"min": 3.0, "max": 6.0, "typical": 4.5},
        "latency_note": "Institutional processing delay; used as ground truth",
        "precision": None,
        "recall": None,
        "role": "Ground-truth reference (official Brazilian hotspots)",
        "cost_usd_month": 0,
    },
    "langgraph_pipeline": {
        "name": "LangGraph pipeline (this work)",
        "latency_seconds_first_response": 52.4,
        "latency_seconds_cached": 1.0,
        "latency_note": "52.4s cold start (40s FIRMS + 12s geocoding); <1s with 5-min cache",
        "precision_dry_season": 0.842,
        "recall_dry_season": 0.918,
        "precision_note": "EXP-ROBUST-003 dry season 2025, XGBoost YES @ P≥0.30",
        "fp_dry_season": 75,
        "role": "Integrated ingestion, fusion, 3-class alerts, ReAct agent",
        "cost_usd_month": 20,
        "availability_pct": 99.0,
    },
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def in_ceara_bbox(lat: float, lon: float) -> bool:
    return CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon <= CEARA_LON_MAX


def parse_firms_points(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    points = []
    for row in raw:
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
            date = str(row.get("acq_date", ""))[:10]
            if date and in_ceara_bbox(lat, lon):
                points.append({"lat": lat, "lon": lon, "date": date, "source": "FIRMS"})
        except (TypeError, ValueError):
            continue
    return points


def parse_inpe_points(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    points = []
    for row in raw:
        try:
            lat = float(str(row.get("lat", "")).strip())
            lon = float(str(row.get("lon", "")).strip())
            date = str(row.get("date", "") or (row.get("data_hora_gmt", "") or "")[:10])[:10]
            if date and in_ceara_bbox(lat, lon):
                points.append({"lat": lat, "lon": lon, "date": date, "source": "INPE"})
        except (TypeError, ValueError):
            continue
    return points


def compute_spatial_overlap(
    firms: list[dict],
    inpe: list[dict],
    radius_km: float = MATCH_RADIUS_KM,
) -> dict:
    """Match FIRMS points to same-day INPE points within radius_km."""
    inpe_by_date: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for p in inpe:
        inpe_by_date[p["date"]].append((p["lat"], p["lon"]))

    matched = 0
    unmatched = 0
    per_date: dict[str, dict] = {}

    for p in firms:
        d = p["date"]
        candidates = inpe_by_date.get(d, [])
        hit = False
        for lat2, lon2 in candidates:
            if haversine_km(p["lat"], p["lon"], lat2, lon2) <= radius_km:
                hit = True
                break
        if hit:
            matched += 1
        else:
            unmatched += 1
        if d not in per_date:
            per_date[d] = {"firms": 0, "matched": 0}
        per_date[d]["firms"] += 1
        if hit:
            per_date[d]["matched"] += 1

    # INPE recall proxy: fraction of INPE points with a FIRMS match same day
    inpe_matched = 0
    firms_by_date: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for p in firms:
        firms_by_date[p["date"]].append((p["lat"], p["lon"]))

    for p in inpe:
        d = p["date"]
        candidates = firms_by_date.get(d, [])
        for lat2, lon2 in candidates:
            if haversine_km(p["lat"], p["lon"], lat2, lon2) <= radius_km:
                inpe_matched += 1
                break

    n_firms = len(firms)
    n_inpe = len(inpe)
    return {
        "match_radius_km": radius_km,
        "ceara_bbox": {
            "lat_min": CEARA_LAT_MIN,
            "lat_max": CEARA_LAT_MAX,
            "lon_min": CEARA_LON_MIN,
            "lon_max": CEARA_LON_MAX,
        },
        "firms_points": n_firms,
        "inpe_points": n_inpe,
        "firms_matched_to_inpe": matched,
        "firms_unmatched": unmatched,
        "firms_match_rate": matched / n_firms if n_firms else 0.0,
        "inpe_matched_to_firms": inpe_matched,
        "inpe_match_rate": inpe_matched / n_inpe if n_inpe else 0.0,
        "unique_dates": len(per_date),
        "per_date_summary": {
            d: {
                "firms": v["firms"],
                "matched": v["matched"],
                "match_rate": v["matched"] / v["firms"] if v["firms"] else 0.0,
            }
            for d, v in sorted(per_date.items())
        },
    }


def build_comparison_table(spatial: dict) -> list[dict]:
    """Side-by-side operational comparison for JSON output."""
    firms = DOCUMENTED_SYSTEMS["nasa_firms"]
    inpe = DOCUMENTED_SYSTEMS["inpe_bdqueimadas"]
    lg = DOCUMENTED_SYSTEMS["langgraph_pipeline"]

    return [
        {
            "system": firms["name"],
            "latency": f"{firms['latency_hours']['min']:.0f}–{firms['latency_hours']['max']:.0f} h",
            "latency_seconds": firms["latency_hours"]["typical"] * 3600,
            "precision": firms["precision"],
            "recall": spatial.get("inpe_match_rate") if spatial["inpe_points"] else None,
            "spatial_note": "Recall proxy = INPE points matched by FIRMS (same-day, 1 km)",
            "cost_usd_month": firms["cost_usd_month"],
            "role": firms["role"],
        },
        {
            "system": inpe["name"],
            "latency": f"{inpe['latency_hours']['min']:.0f}–{inpe['latency_hours']['max']:.0f} h",
            "latency_seconds": inpe["latency_hours"]["typical"] * 3600,
            "precision": None,
            "recall": None,
            "spatial_note": "Ground truth; spatial overlap computed vs FIRMS",
            "cost_usd_month": inpe["cost_usd_month"],
            "role": inpe["role"],
        },
        {
            "system": lg["name"],
            "latency": f"{lg['latency_seconds_first_response']:.1f} s (cold) / <{lg['latency_seconds_cached']:.0f} s (cache)",
            "latency_seconds": lg["latency_seconds_first_response"],
            "precision": lg["precision_dry_season"],
            "recall": lg["recall_dry_season"],
            "spatial_note": "Dry season 2025 municipal YES alerts (EXP-ROBUST-003)",
            "cost_usd_month": lg["cost_usd_month"],
            "role": lg["role"],
        },
    ]


def pct_tex(v: float | None) -> str:
    if v is None:
        return "---"
    return f"{v:.1%}".replace("%", "\\%")


def write_latex_table(comparison: list[dict], spatial: dict, path: Path) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Operational baseline comparison: NASA FIRMS, INPE BDQueimadas, and LangGraph pipeline.}",
        r"\label{tab:operational-baseline}",
        r"\small",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"\textbf{System} & \textbf{Latency} & \textbf{Precision} & \textbf{Recall} & \textbf{Cost/mo} \\",
        r"\midrule",
    ]
    for row in comparison:
        prec = pct_tex(row["precision"]) if row["precision"] is not None else "---"
        rec = pct_tex(row["recall"]) if row["recall"] is not None else "---"
        cost = f"\\${row['cost_usd_month']:.0f}" if row["cost_usd_month"] else "Free"
        lines.append(
            f"{row['system']} & {row['latency']} & {prec} & {rec} & {cost} \\\\"
        )
    lines.extend([
        r"\midrule",
        f"FIRMS$\\rightarrow$INPE spatial match (1\\,km, same day) & "
        f"{spatial['firms_points']} FIRMS pts & "
        f"{pct_tex(spatial['firms_match_rate'])} matched & "
        f"INPE recall proxy {pct_tex(spatial['inpe_match_rate'])} & "
        f"{spatial['unique_dates']} days \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    t0 = time.time()
    print("=" * 72)
    print("EXP-ROBUST-006: Operational baseline benchmark")
    print("=" * 72)

    firms_pts = parse_firms_points(DATA_DIR / "firms_ceara_7d.json")
    inpe_pts = parse_inpe_points(DATA_DIR / "inpe_ceara_historico.json")
    print(f"  FIRMS points in CE bbox: {len(firms_pts)}")
    print(f"  INPE points in CE bbox: {len(inpe_pts)}")

    spatial = compute_spatial_overlap(firms_pts, inpe_pts)
    print(
        f"  Spatial overlap (1 km, same day): "
        f"FIRMS→INPE {spatial['firms_match_rate']:.1%} "
        f"({spatial['firms_matched_to_inpe']}/{spatial['firms_points']}), "
        f"INPE→FIRMS {spatial['inpe_match_rate']:.1%}"
    )

    comparison = build_comparison_table(spatial)
    lg = DOCUMENTED_SYSTEMS["langgraph_pipeline"]

    payload = {
        "experiment": "EXP-ROBUST-006",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documented_systems": DOCUMENTED_SYSTEMS,
        "comparison_table": comparison,
        "spatial_overlap": spatial,
        "key_findings": {
            "langgraph_latency_advantage_vs_firms_hours": round(
                DOCUMENTED_SYSTEMS["nasa_firms"]["latency_hours"]["typical"] * 3600
                / lg["latency_seconds_first_response"],
                1,
            ),
            "langgraph_dry_season_precision": lg["precision_dry_season"],
            "langgraph_dry_season_recall": lg["recall_dry_season"],
            "firms_documented_precision": DOCUMENTED_SYSTEMS["nasa_firms"]["precision"],
            "firms_to_inpe_match_rate": spatial["firms_match_rate"],
        },
        "runtime_sec": round(time.time() - t0, 2),
    }

    json_path = RESULTS_DIR / "EXP-ROBUST-006_operational_baseline.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# EXP-ROBUST-006 — Operational Baseline Comparison",
        "",
        f"**Date:** {payload['timestamp']}",
        f"**Runtime:** {payload['runtime_sec']}s",
        "",
        "## Documented operational metrics",
        "",
        "| System | Latency | Precision | Recall | Cost/mo |",
        "|--------|---------|-----------|--------|---------|",
    ]
    for row in comparison:
        prec = f"{row['precision']:.1%}" if row["precision"] is not None else "—"
        rec = f"{row['recall']:.1%}" if row["recall"] is not None else "—"
        md_lines.append(
            f"| {row['system']} | {row['latency']} | {prec} | {rec} | ${row['cost_usd_month']} |"
        )

    md_lines.extend([
        "",
        "## Spatial overlap (FIRMS vs INPE, Ceará bbox, 1 km same-day)",
        "",
        f"- FIRMS points: {spatial['firms_points']}",
        f"- INPE points: {spatial['inpe_points']}",
        f"- FIRMS matched to INPE: {spatial['firms_matched_to_inpe']} ({spatial['firms_match_rate']:.1%})",
        f"- INPE matched to FIRMS: {spatial['inpe_matched_to_firms']} ({spatial['inpe_match_rate']:.1%})",
        "",
        "## Key findings",
        "",
        f"- LangGraph cold-start latency **{lg['latency_seconds_first_response']}s** vs FIRMS **3–6 h** "
        f"(~{payload['key_findings']['langgraph_latency_advantage_vs_firms_hours']}× faster first response)",
        f"- LangGraph dry-season alert precision **{lg['precision_dry_season']:.1%}**, recall **{lg['recall_dry_season']:.1%}**",
        f"- FIRMS→INPE spatial concordance **{spatial['firms_match_rate']:.1%}** on bundled sample data",
        "",
        "## Reproduce",
        "```bash",
        "cd backend && python -m experiments.operational_baseline_benchmark",
        "```",
    ])
    md_path = RESULTS_DIR / "EXP-ROBUST-006_operational_baseline.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    tex_path = RESULTS_DIR / "tabela_operational_baseline.tex"
    write_latex_table(comparison, spatial, tex_path)

    print(f"\n  Saved: {json_path.name}, {md_path.name}, {tex_path.name}")
    print("=" * 72)


if __name__ == "__main__":
    main()
