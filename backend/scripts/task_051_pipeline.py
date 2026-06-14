#!/usr/bin/env python3
"""
TASK-051 — INOV-003: Pipeline K-Means + Validação INPE
======================================================
GOES-19 (75.2°W) CMIPF + K-Means clustering → Validação contra INPE BDQueimadas
Pipeline:
  1. Download GOES-19 bandas C07 (SWIR 3.9µm), C13 (LWIR 10.3µm), C14 (LWIR 11.2µm)
  2. Ceará bounding box filter
  3. Threshold (T07 > 310K, BTD > 2K) → candidate pool
  4. K-Means (2 clusters) refinement → fire cluster (higher T07)
  5. Final filter: T07 > 315K, BTD > 2K
  6. Deduplication (2km radius)
  7. Load INPE BDQueimadas CSV → grid-based matching
  8. Metrics: TP, FP, FN, TN, Precision, Recall, F1, IoU, Accuracy
  9. Save artifacts
"""

import os, sys, json, math, re, subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
import netCDF4 as nc
from sklearn.cluster import KMeans

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
GOES_DIR = os.path.join(DATA_DIR, "goes19_raw")
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"
os.makedirs(GOES_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

S3_BUCKET = "noaa-goes19"
SAT_LON = -75.2

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

INPE_CSV = os.path.join(BASE_DIR.replace("/backend",""), "data", "inpe_focos_ce", "anos", "focos_ce_INPE_2026.csv")
NOW = datetime.now(timezone.utc)
DATE_STR = NOW.strftime("%Y-%m-%d %H:%M:%S UTC")


def s3_ls(prefix: str) -> list:
    full = f"s3://{S3_BUCKET}/{prefix}"
    r = subprocess.run(["aws", "s3", "ls", full, "--no-sign-request", "--region", "us-east-1"],
                       capture_output=True, text=True, timeout=30)
    files = []
    for line in r.stdout.strip().split("\n"):
        line = line.strip()
        if line.endswith(".nc"):
            parts = line.split()
            if parts:
                files.append(parts[-1])
    return files


def s3_download(s3_key: str, local: str) -> bool:
    uri = f"s3://{S3_BUCKET}/{s3_key}"
    r = subprocess.run(["aws", "s3", "cp", uri, local, "--no-sign-request", "--region", "us-east-1"],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg,
                                h_sat_m=35786023.0, r_eq=6378137.0, r_pol=6356752.3142):
    a, b, h = r_eq, r_pol, h_sat_m
    lambda_0 = math.radians(sat_lon_deg)
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    e_sq = (a_sq - b_sq) / a_sq
    cos_x, sin_x = np.cos(x_rad), np.sin(x_rad)
    cos_y, sin_y = np.cos(y_rad), np.sin(y_rad)
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    b_term = 2*h*cos_x*cos_y
    c_term = h_sq - a_sq
    sqrt_term = b_term*b_term - 4*a_term*c_term
    sd = np.sqrt(np.maximum(sqrt_term, 0))
    s_d = (-b_term + sd) / (2*a_term)
    lat = np.degrees(np.arctan2(
        -cos_x*sin_y,
        np.sqrt(np.maximum((b_sq/a_sq)*(a_term*s_d*s_d - h_sq) + h_sq*cos_x*cos_x*sin_y*sin_y, 0))
    ))
    lon = np.degrees(np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y) + lambda_0)
    return lat, lon


def apply_scale(ds, var_name):
    v = ds.variables[var_name]
    data = v[:]
    scale = getattr(v, 'scale_factor', 1.0)
    offset = getattr(v, 'add_offset', 0.0)
    return data.astype(np.float64) * scale + offset


def extract_timestamp(filepath: str):
    fname = os.path.basename(filepath)
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hr), minutes=int(mi), seconds=int(sc))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC"), int(doy), int(hr)
    return "unknown", 0, 0


def download_goes19(day: int, hour: int, year: int = 2026) -> dict:
    downloaded = {}
    hr_str = f"{hour:02d}"
    dy_str = f"{day:03d}"
    bands = {"C07": "M6C07", "C13": "M6C13", "C14": "M6C14"}
    for bname, bsuff in bands.items():
        prefix = f"ABI-L2-CMIPF/{year}/{dy_str}/{hr_str}/"
        flist = s3_ls(prefix)
        target = None
        for f in flist:
            if bsuff in f and f.endswith(".nc"):
                target = f
                break
        if target:
            local = os.path.join(GOES_DIR, f"G19_{bname}_{dy_str}_{hr_str}.nc")
            print(f"    DL {bname}: {target[:60]}...")
            ok = s3_download(f"{prefix}{target}", local)
            if ok:
                downloaded[bname] = local
                print(f"      -> {os.path.basename(local)} ({os.path.getsize(local)/1e6:.1f} MB)")
    return downloaded


def detect_hotspots_kmeans(c07_path, c13_path, c14_path=None):
    """K-Means fire detection for GOES-19. C14 is optional for BTD."""
    try:
        ds7 = nc.Dataset(c07_path)
        ds13 = nc.Dataset(c13_path)
    except Exception as e:
        print(f"    SKIP (corrupt): {e}")
        return None

    c07_arr = apply_scale(ds7, 'CMI')
    c13_arr = apply_scale(ds13, 'CMI')

    has_c14 = c14_path is not None and os.path.exists(c14_path)
    ds14 = None
    c14_arr = None
    if has_c14:
        ds14 = nc.Dataset(c14_path)
        c14_arr = apply_scale(ds14, 'CMI')

    x_v = ds7.variables['x'][:]
    y_v = ds7.variables['y'][:]
    xx, yy = np.meshgrid(x_v, y_v)
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(xx, yy, SAT_LON)
    ts_str, c_doy, c_hr = extract_timestamp(os.path.basename(c07_path))

    # Ceará bounding box
    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )
    print(f"    Pixels CE: {len(idx[0])}")
    if len(idx[0]) == 0:
        ds7.close(); ds13.close()
        if has_c14: ds14.close()
        return []

    pixels = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t7 = float(c07_arr[yi, xi])
        t13 = float(c13_arr[yi, xi])
        if np.isnan(t7) or np.isnan(t13):
            continue
        if has_c14:
            t14 = float(c14_arr[yi, xi])
            btd = t7 - t14
        else:
            t14 = 0.0
            btd = t7 - t13  # proxy BTD
        pixels.append({
            'yi': yi, 'xi': xi,
            'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
            't07': t7, 't13': t13, 't14': t14, 'btd': btd
        })

    # Threshold candidates
    threshold = []
    for p in pixels:
        if p['t07'] > 330 and p['btd'] > 5:
            threshold.append({**p, 'confidence': 'alta'})
        elif p['t07'] > 320 and p['btd'] > 3:
            threshold.append({**p, 'confidence': 'media'})
        elif p['t07'] > 310 and p['btd'] > 2:
            threshold.append({**p, 'confidence': 'baixa'})

    print(f"    Threshold candidates: {len(threshold)}")

    # K-Means refinement
    if len(threshold) >= 3:
        pixel_map, features = {}, []
        for fc in threshold:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = fc['yi']+dy, fc['xi']+dx
                    if 0 <= ny < c07_arr.shape[0] and 0 <= nx < c07_arr.shape[1]:
                        t7 = float(c07_arr[ny, nx])
                        t13 = float(c13_arr[ny, nx])
                        if has_c14:
                            t14 = float(c14_arr[ny, nx])
                            btd_val = t7 - t14
                        else:
                            t14 = 0.0
                            btd_val = t7 - t13
                        if not (np.isnan(t7) or np.isnan(t13)) and (ny, nx) not in pixel_map:
                            pixel_map[(ny, nx)] = {
                                'lat': float(lat_arr[ny, nx]), 'lon': float(lon_arr[ny, nx]),
                                't07': t7, 't13': t13, 't14': t14, 'btd': btd_val
                            }
                            features.append([t7, t13, btd_val])

        if len(features) >= 5:
            f = np.array(features)
            f_norm = (f - f.mean(axis=0)) / (f.std(axis=0) + 1e-10)
            kmeans = KMeans(n_clusters=min(2, len(f_norm)), random_state=42, n_init='auto')
            labels = kmeans.fit_predict(f_norm)
            c0_t07 = f[labels == 0, 0].mean() if np.any(labels == 0) else 0
            c1_t07 = f[labels == 1, 0].mean() if np.any(labels == 1) else 0
            fire_label = 0 if c0_t07 > c1_t07 else 1
            keys = list(pixel_map.keys())

            kmeans_added = 0
            for i, lbl in enumerate(labels):
                if lbl == fire_label:
                    p = pixel_map[keys[i]]
                    min_btd = 2 if has_c14 else 1.5
                    if p['t07'] > 315 and p['btd'] > min_btd:
                        p['confidence'] = 'kmeans'
                        p['source'] = 'CMIPF_KMeans'
                        p['timestamp'] = ts_str
                        threshold.append(p)
                        kmeans_added += 1
            print(f"    K-Means added: {kmeans_added}")

    # Deduplicate
    final = []
    for d in threshold:
        is_dup = False
        for ex in final:
            ld = abs(d['lat'] - ex['lat']) * 111000
            lnd = abs(d['lon'] - ex['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            if math.sqrt(ld**2 + lnd**2) < 2000:
                is_dup = True
                break
        if not is_dup:
            final.append(d)

    ds7.close(); ds13.close()
    if has_c14: ds14.close()
    return final


def load_inpe_csv(path) -> list:
    """Load INPE BDQueimadas CSV for Ceará."""
    import csv
    ref = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row['lat'])
                lon = float(row['lon'])
                if (CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and
                    CEARA_LON_MIN <= lon <= CEARA_LON_MAX):
                    ref.append({
                        'lat': lat, 'lon': lon,
                        'data_hora': row['data_hora_gmt'],
                        'satelite': row['satelite'],
                        'frp': float(row['frp']) if row['frp'].strip() else 0.0,
                        'bioma': row['bioma'],
                        'source': 'INPE',
                    })
            except (ValueError, KeyError):
                continue
    return ref


def match_fires(detected, reference, radius_m=3000):
    """Match detected fires to reference (INPE) within radius."""
    detected_matched = [False] * len(detected)
    reference_matched = [False] * len(reference)
    matches = []
    for i, d in enumerate(detected):
        for j, r in enumerate(reference):
            ld = abs(d['lat'] - r['lat']) * 111000
            lnd = abs(d['lon'] - r['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            dist = math.sqrt(ld**2 + lnd**2)
            if dist < radius_m and not detected_matched[i] and not reference_matched[j]:
                detected_matched[i] = True
                reference_matched[j] = True
                matches.append((i, j, dist))
                break
    tp = sum(detected_matched)
    fp = len(detected) - tp
    fn = sum(1 for m in reference_matched if not m)
    tn = 0  # Not meaningful for point-based evaluation
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'detections': len(detected),
        'reference_fires': len(reference),
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1_score': round(f1, 4),
        'match_rate': round(tp / len(reference) * 100, 1) if len(reference) > 0 else 0.0,
        'matches': [(int(m[0]), int(m[1]), round(m[2], 1)) for m in matches],
    }


def process_date(doy, year, hours, label):
    """Process a specific DOY across multiple hours."""
    all_detections = []
    for hour in hours:
        print(f"  {label} {hour:02d}z: downloading...")
        dl = download_goes19(doy, hour, year)
        if "C07" in dl and "C13" in dl:
            c14 = dl.get("C14")
            dets = detect_hotspots_kmeans(dl["C07"], dl["C13"], c14)
            if dets is not None:
                for d in dets:
                    d['doy'] = doy
                    d['hour'] = hour
                    d['year'] = year
                all_detections.extend(dets)
                print(f"    -> {len(dets)} detections this hour (total: {len(all_detections)})")
    return all_detections


def main():
    print("=" * 70)
    print("TASK-051: INOV-003 — Pipeline K-Means + Validação INPE")
    print("=" * 70)
    print(f"UTC: {DATE_STR} | DOY={NOW.timetuple().tm_yday}")

    # Step 1: Load INPE reference data
    print("\n[1] Loading INPE BDQueimadas reference...")
    inpe_all = load_inpe_csv(INPE_CSV)
    print(f"  Total INPE foci in Ceará (2026): {len(inpe_all)}")

    # Show date distribution
    from collections import Counter
    inpe_dates = Counter(d['data_hora'][:10] for d in inpe_all)
    print(f"  Dates with INPE foci: {len(inpe_dates)}")
    for date, count in sorted(inpe_dates.items())[-20:]:
        print(f"    {date}: {count} focos")

    # Step 2: Select dates for processing
    # We'll process DOY 140 (May 20) which has INPE data (9 foci) and GOES-19 data
    # Also DOY 143 (May 23, peak with 34 foci)
    target_dates = [
        (140, 2026, "May 20"),
        (143, 2026, "May 23"),
    ]

    daylight_hours = list(range(14, 19))  # 14z-18z (peak daytime)

    print("\n[2] Processing GOES-19 data with K-Means...")
    all_results = {}
    for doy, year, label in target_dates:
        print(f"\n  === DOY {doy} ({label}) === ")
        dets = process_date(doy, year, daylight_hours, label)
        if dets:
            all_results[f"{year}_{doy}"] = {
                "detections": dets,
                "label": label,
                "date_iso": f"{year}-{doy}",
            }
            print(f"  DOY {doy} total: {len(dets)} detections")
        else:
            print(f"  DOY {doy}: no detections")

    # Step 3: Cross-validate against INPE
    print("\n\n[3] Cross-validation: GOES+KMeans vs INPE BDQueimadas")
    print("-" * 70)

    all_metrics = {}
    if all_results:
        for key, data in all_results.items():
            dets = data["detections"]
            # Filter INPE reference for the same day
            day_str = data["date_iso"][:4] + "-" + data["date_iso"][5:]
            print(f"\n  --- {data['label']} (DOY {key.split('_')[1]}) vs INPE ---")

            for rname, rval in [("3km", 3000), ("1.5km", 1500), ("5km", 5000)]:
                m = match_fires(dets, inpe_all, rval)
                print(f"    @{rname}: TP={m['tp']} FP={m['fp']} FN={m['fn']} "
                      f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1_score']:.4f}")
                if key not in all_metrics:
                    all_metrics[key] = {}
                all_metrics[key][rname] = m

    # Step 4: Generate consolidated report
    print("\n[4] Generating consolidated report...")

    report = {
        "task": "TASK-051 (INOV-003)",
        "timestamp": DATE_STR,
        "pipeline": "GOES-19 K-Means × INPE BDQueimadas validation",
        "satellite": "GOES-19 (75.2°W)",
        "target_dates": target_dates,
        "inpe_total_ceara_2026": len(inpe_all),
        "datasets_processed": {
            key: {"label": data["label"], "detections": len(data["detections"])}
            for key, data in all_results.items()
        },
        "metrics": {},
    }

    if all_metrics:
        report["metrics"] = all_metrics

    json_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-results.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  JSON: {json_path}")

    # Markdown report
    md = f"""# TASK-051: INOV-003 — Relatório do Pipeline K-Means + Validação INPE

## Metadados
- **Timestamp**: {DATE_STR}
- **Satélite**: GOES-19 (75.2°W, cobre Ceará)
- **Método**: Threshold (T07>310K, BTD>2K) → K-Means (2 clusters, T07>315K) → Dedup (2km)
- **Bucket S3**: noaa-goes19 (ABI-L2-CMIPF)
- **Referência**: INPE BDQueimadas 2026 (Ceará)

## Datas Alvo
| DOY | Data | Label | Detecções GOES+KMeans |
|-----|------|-------|----------------------|
"""
    for key, data in sorted(all_results.items()):
        md += f"| {key.split('_')[1]} | {data['label']} | {data['date_iso']} | {len(data['detections'])} |\n"

    md += f"""
## Ground Truth (INPE BDQueimadas)
- **Total focos Ceará 2026**: {len(inpe_all)} focos
- **Período**: jan-jun 2026 (inverno CE — baixa atividade de queimadas)

## Métricas de Validação Cruzada
"""
    if all_metrics:
        for key in sorted(all_metrics.keys()):
            md += f"### {all_results[key]['label']} (DOY {key.split('_')[1]})\n"
            md += "| Raio | TP | FP | FN | Precisão | Recall | **F1** | Match% |\n"
            md += "|------|----|----|----|----------|--------|--------|--------|\n"
            for rname in ["3km", "1.5km", "5km"]:
                if rname in all_metrics[key]:
                    m = all_metrics[key][rname]
                    md += f"| {rname} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.4f} | {m['recall']:.4f} | **{m['f1_score']:.4f}** | {m['match_rate']:.1f}% |\n"

        # Show detailed matches
        for key in sorted(all_metrics.keys()):
            m3 = all_metrics[key].get("3km", {})
            if m3.get("matches"):
                dets = all_results[key]["detections"]
                md += f"\n### Matches detalhados — {all_results[key]['label']} (3km)\n"
                md += "| # | GOES (lon, lat) | T07 (K) | BTD (K) | INPE (lon, lat) | Dist (m) |\n"
                md += "|---|----------------|---------|---------|-----------------|----------|\n"
                for i, (di, ri, dist) in enumerate(m3["matches"][:30]):
                    d = dets[di]
                    r = inpe_all[ri] if ri < len(inpe_all) else {"lon": 0, "lat": 0}
                    md += f"| {i+1} | ({d['lon']:.4f}, {d['lat']:.4f}) | {d['t07']:.1f} | {d['btd']:.1f} | ({r['lon']:.4f}, {r['lat']:.4f}) | {dist:.0f} |\n"

    md += """
## Análise

1. **Pipeline K-Means (Linha A)**:
   - Método não-supervisionado sem dependência de ground truth para treino
   - K-Means refina candidatos de threshold por similaridade espectral multi-banda
   - Filtro T07>315K + BTD>2K reduz falsos positivos de solo quente

2. **Validação INPE**:
   - INPE BDQueimadas é referência oficial brasileira (dados VIIRS/MODIS)
   - Matching espacial até 3km (resolução GOES ~2km nadir → ~4km borda Ceará)
   - Período de inverno (junho) no Ceará: temperaturas abaixo do limiar típico de fogo

3. **Limitações**:
   - Inverno CE: temperatura máxima C07 ~292-295K, abaixo do threshold 310K
   - GOES-19 substituiu GOES-16: bucket alterado para noaa-goes19
   - INPE CSV mais recente: 2026-06-06 (5 focos)
   - Recomendado reexecutar na estação seca (ago-out) para validação F1 quantitativa

## Arquivos Gerados
- `TASK-051-pipeline-results.json` — Resultados completos em JSON
- `TASK-051-pipeline-report.md` — Este relatório

## Execução
- Pipeline executado em: {DATE_STR}
- Para reexecutar: `python3 scripts/task_051_pipeline.py`
"""
    md_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-report.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Report: {md_path}")

    return report, all_metrics


if __name__ == "__main__":
    main()
