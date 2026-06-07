"""
Avaliação **à escala da imagem GOES** (pixels do recorte CE) vs **focos INPE pontuais**.

A grade grossa (ex.: 72×72) dilui focos quase pontuais e empobrece F1. Aqui:

1. Mantém a resolução nativa do recorte ABI no bbox do Ceará.
2. Calcula o score ``hourly_anomaly_score`` por hora (multi-banda quando disponível).
3. Fusão temporal por **máximo** do score entre horas.
4. Limiar por percentil (``contamination``) nos pixels válidos.
5. Agrupa pixéis quentes em componentes conexas; faz **correspondência greedy** foco↔cluster
   se distância (Haversine) centroid–foco ≤ ``match_radius_km``.
6. Métricas tipo deteção: TP = pares foco–cluster; precision = TP/(TP+FP); recall = TP/(TP+FN); F1.

Uso::

    python -m src.pixel_inpe_eval \\
      --inpe-csv data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv \\
      --date 2024-10-31 \\
      --hours-utc 16,17,18 \\
      --channels 7,13,14 \\
      --raw-dir data/goes16_raw \\
      --skip-download \\
      --match-radius-km 15 \\
      --contamination 0.08
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.ndimage import binary_opening, label

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config.ceara_config import CEARA_BBOX  # noqa: E402
from src.goes_fire_digital_twin import hourly_anomaly_score  # noqa: E402
from src.unsupervised_fire_goes import (  # noqa: E402
    ensure_goes_netcdf,
    find_local_goes_nc,
    load_goes_bt_crop,
    load_inpe_focos,
)


def haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Distâncias em km de um ponto a grades lat/lon."""
    r = 6371.0
    p1 = np.radians(lat1)
    t1 = np.radians(lon1)
    p2 = np.radians(lat2)
    t2 = np.radians(lon2)
    dlat = p2 - p1
    dlon = t2 - t1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def haversine_km_scalar(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return float(haversine_km(lat1, lon1, np.array([lat2]), np.array([lon2]))[0])


def collect_hourly_pixel_slots(
    day_utc: date,
    hours_utc: Sequence[int],
    channels: Sequence[int],
    bbox: dict,
    raw_dir: Path,
    *,
    skip_download: bool,
    overwrite: bool,
    use_dqf: bool,
    show_progress: bool,
) -> Tuple[List[Dict[int, np.ndarray]], List[str], np.ndarray, np.ndarray]:
    """Slots ``{canal: BT}`` por hora + lat/lon da primeira leitura (mesma grade ABI)."""
    hourly: List[Dict[int, np.ndarray]] = []
    nc_refs: List[str] = []
    lat0: np.ndarray | None = None
    lon0: np.ndarray | None = None

    if skip_download and len(hours_utc) > 1:
        warnings.warn(
            "Com --skip-download confirme que existem NetCDF por hora UTC "
            "(o código filtra por ``_s{ano}{día}{hora}`` no nome).",
            stacklevel=2,
        )

    for hour in hours_utc:
        when = datetime(day_utc.year, day_utc.month, day_utc.day, int(hour), tzinfo=timezone.utc)
        slot: Dict[int, np.ndarray] = {}
        for ch in channels:
            if skip_download:
                path = find_local_goes_nc(raw_dir, day_utc, ch, hour_utc=int(hour))
            else:
                path = ensure_goes_netcdf(when, ch, raw_dir, overwrite=overwrite, show_progress=show_progress)
            nc_refs.append(str(path))
            bt, lat, lon, valid = load_goes_bt_crop(path, bbox=bbox, dqf_good_only=use_dqf)
            if lat0 is None:
                lat0, lon0 = lat, lon
            slot[int(ch)] = np.where(valid, bt, np.nan).astype(np.float64)
        hourly.append(slot)

    assert lat0 is not None and lon0 is not None
    return hourly, nc_refs, lat0, lon0


def fuse_max_hourly_scores(
    hourly: List[Dict[int, np.ndarray]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Máximo do score de anomalia entre horas; ``vb`` = válido em pelo menos uma hora."""
    stacks: List[np.ndarray] = []
    vb_any = None
    for slot in hourly:
        s, v = hourly_anomaly_score(slot)
        stacks.append(np.where(v, s, np.nan))
        vb_any = v if vb_any is None else (vb_any | v)
    assert vb_any is not None
    cube = np.stack(stacks, axis=0)
    with np.errstate(all="ignore"):
        S = np.nanmax(cube, axis=0)
    S = np.where(np.all(~np.isfinite(cube), axis=0), np.nan, S)
    vb = vb_any & np.isfinite(S)
    return S, vb


def cluster_centroids(
    lab: np.ndarray,
    nlab: int,
    lat: np.ndarray,
    lon: np.ndarray,
) -> List[Tuple[int, float, float, int]]:
    """Lista (label_id, clat, clon, n_pixels)."""
    out: List[Tuple[int, float, float, int]] = []
    for k in range(1, nlab + 1):
        m = lab == k
        npx = int(np.sum(m))
        clat = float(np.mean(lat[m]))
        clon = float(np.mean(lon[m]))
        out.append((k, clat, clon, npx))
    return out


def greedy_match_focos_to_clusters(
    centroids: List[Tuple[int, float, float, int]],
    df_focos: pd.DataFrame,
    radius_km: float,
) -> Tuple[int, int, int]:
    """
    Retorna (TP, FP, FN) com correspondência 1:1 greedy (foco escolhe cluster mais próximo dentro do raio).
    TP = número de pares; FP = clusters não usados; FN = focos não pareados.
    """
    if df_focos.empty:
        return 0, len(centroids), 0

    unused_c = set(range(len(centroids)))
    matched_f = 0
    for _, row in df_focos.iterrows():
        flat, flon = float(row["lat"]), float(row["lon"])
        best_j: int | None = None
        best_d = float("inf")
        for j in list(unused_c):
            _, clat, clon, _ = centroids[j]
            d = haversine_km_scalar(flat, flon, clat, clon)
            if d <= radius_km and d < best_d:
                best_d = d
                best_j = j
        if best_j is not None:
            unused_c.remove(best_j)
            matched_f += 1

    tp = matched_f
    fp = len(unused_c)
    fn = len(df_focos) - tp
    return tp, fp, fn


def evaluate_pixel_day(
    day_utc: date,
    df_inpe: pd.DataFrame,
    *,
    hours_utc: Sequence[int],
    channels: Sequence[int],
    bbox: dict,
    raw_dir: Path,
    skip_download: bool,
    overwrite: bool,
    use_dqf: bool,
    show_progress: bool,
    contamination: float,
    match_radius_km: float,
    min_cluster_pixels: int,
    morph_open: int,
) -> Dict[str, Any]:
    hourly, nc_refs, lat, lon = collect_hourly_pixel_slots(
        day_utc,
        hours_utc,
        channels,
        bbox,
        raw_dir,
        skip_download=skip_download,
        overwrite=overwrite,
        use_dqf=use_dqf,
        show_progress=show_progress,
    )
    S, vb = fuse_max_hourly_scores(hourly)
    if not vb.any():
        return {"error": "sem pixels válidos", "day": str(day_utc)}

    c = float(min(max(contamination, 0.001), 0.5))
    thr = float(np.percentile(S[vb], 100.0 * (1.0 - c)))
    hot = (S >= thr) & vb

    if morph_open > 0:
        struct = np.ones((3, 3), dtype=bool)
        for _ in range(morph_open):
            hot = binary_opening(hot, structure=struct)

    lab, nlab = label(hot)
    centroids_all = cluster_centroids(lab, nlab, lat, lon)
    centroids = [t for t in centroids_all if t[3] >= min_cluster_pixels]

    d0 = datetime(day_utc.year, day_utc.month, day_utc.day, tzinfo=timezone.utc)
    d1 = d0 + pd.Timedelta(days=1)
    df_day = df_inpe.loc[(df_inpe["datetime"] >= d0) & (df_inpe["datetime"] < d1)]

    clusters_for_match = [(i, c[1], c[2], c[3]) for i, c in enumerate(centroids)]

    tp, fp, fn = greedy_match_focos_to_clusters(clusters_for_match, df_day, match_radius_km)

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "day": day_utc.isoformat(),
        "eval_mode": "pixel_image_inpe_focos",
        "contamination": c,
        "score_threshold": thr,
        "match_radius_km": float(match_radius_km),
        "min_cluster_pixels": int(min_cluster_pixels),
        "n_focos_inpe_day": int(len(df_day)),
        "n_hot_pixels": int(np.sum(hot)),
        "n_clusters": len(centroids),
        "n_clusters_raw": int(nlab),
        "tp_pairs": int(tp),
        "fp_clusters": int(fp),
        "fn_focos": int(fn),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "hours_utc": list(hours_utc),
        "channels": list(channels),
        "shape_hw": list(S.shape),
        "goes_refs_sample": nc_refs[:3] if nc_refs else [],
    }


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Métricas foco-a-pixel: imagem GOES vs INPE")
    p.add_argument("--inpe-csv", type=Path, required=True)
    p.add_argument("--date", type=str, required=True, help="AAAA-MM-DD UTC")
    p.add_argument("--hours-utc", type=str, default="16,17,18")
    p.add_argument("--channels", type=str, default="7,13,14")
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--overwrite-goes", action="store_true")
    p.add_argument("--no-dqf", action="store_true")
    p.add_argument("--no-progress", action="store_true")
    p.add_argument("--contamination", type=float, default=0.08)
    p.add_argument("--match-radius-km", type=float, default=15.0)
    p.add_argument("--min-cluster-pixels", type=int, default=6)
    p.add_argument("--morph-open", type=int, default=0)
    p.add_argument("--output-json", type=Path, default=None)
    args = p.parse_args(argv)

    raw_dir = Path(args.raw_dir) if args.raw_dir else _REPO_ROOT / "data" / "goes16_raw"
    day = datetime.strptime(args.date, "%Y-%m-%d").date()
    hours = [int(x.strip()) for x in args.hours_utc.split(",") if x.strip()]
    chans = sorted({int(x.strip()) for x in args.channels.split(",") if x.strip()})
    if 13 not in chans:
        chans.append(13)
        chans = sorted(set(chans))

    df = load_inpe_focos(args.inpe_csv)
    out = evaluate_pixel_day(
        day,
        df,
        hours_utc=hours,
        channels=chans,
        bbox=CEARA_BBOX,
        raw_dir=raw_dir,
        skip_download=args.skip_download,
        overwrite=args.overwrite_goes,
        use_dqf=not args.no_dqf,
        show_progress=not args.no_progress,
        contamination=float(args.contamination),
        match_radius_km=float(args.match_radius_km),
        min_cluster_pixels=max(1, int(args.min_cluster_pixels)),
        morph_open=max(0, int(args.morph_open)),
    )
    print(json.dumps(out, indent=2))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
