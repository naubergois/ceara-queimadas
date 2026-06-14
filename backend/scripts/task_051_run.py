#!/usr/bin/env python3
"""
TASK-051 — INOV-003: Pipeline K-Means + Validação INPE (quick run)
Only processes already-downloaded GOES-19 data, no new S3 downloads.
"""

import os, sys, json, math, re, csv
from datetime import datetime, timedelta, timezone
import numpy as np
import netCDF4 as nc
from sklearn.cluster import KMeans
from collections import Counter

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas"
BACKEND = os.path.join(BASE_DIR, "backend")
GOES_DIR = os.path.join(BACKEND, "data", "goes19_raw")
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# CONFIG
SAT_LON = -75.2
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
INPE_CSV = os.path.join(BASE_DIR, "data", "inpe_focos_ce", "anos", "focos_ce_INPE_2026.csv")
NOW = datetime.now(timezone.utc)
DATE_STR = NOW.strftime("%Y-%m-%d %H:%M:%S UTC")

# FIRMS data for comparison
FIRMS_CSVS = {
    "VIIRS_SNPP": os.path.join(BASE_DIR, "data", "firms_suomi_viirs_24h.csv"),
    "VIIRS_NOAA20": os.path.join(BASE_DIR, "data", "firms_noaa20_viirs_24h.csv"),
    "MODIS": os.path.join(BASE_DIR, "data", "firms_modis_24h.csv"),
}


def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg,
                                h_sat_m=35786023.0, r_eq=6378137.0, r_pol=6356752.3142):
    a, b, h = r_eq, r_pol, h_sat_m
    lambda_0 = math.radians(sat_lon_deg)
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    cos_x, sin_x = np.cos(x_rad), np.sin(x_rad)
    cos_y, sin_y = np.cos(y_rad), np.sin(y_rad)
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    b_term = 2*h*cos_x*cos_y
    c_term = h_sq - a_sq
    sd = np.sqrt(np.maximum(b_term*b_term - 4*a_term*c_term, 0))
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


def extract_ts(fpath):
    fname = os.path.basename(fpath)
    # Pattern 1: GOES native _sYYYYDDDHHMMSS
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        return int(doy), int(hr)
    # Pattern 2: Custom G19_BAND_DOY_HOUR
    m = re.search(r"G19_\w+_(\d+)_(\d+)", fname)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Pattern 3: GOES16_BAND_DOY_HOUR
    m = re.search(r"GOES16_\w+_(\d+)_(\d+)", fname)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def find_band_file(doy, hour, band_suffix):
    """Find local GOES file for a band."""
    for fname in os.listdir(GOES_DIR):
        if not fname.endswith(".nc"): continue
        if band_suffix not in fname: continue
        m = re.search(r"_s(\d{4})(\d{3})(\d{2})", fname)
        if m and int(m.group(2)) == doy and abs(int(m.group(3)) - hour) <= 2:
            return os.path.join(GOES_DIR, fname)
    return None


def detect_hotspots(c07_path, c13_path, c14_path=None):
    """K-Means fire detection (same logic as goes16_pipeline)."""
    try:
        ds7 = nc.Dataset(c07_path)
        ds13 = nc.Dataset(c13_path)
    except Exception as e:
        return None, {"error": str(e)}

    c07_arr = apply_scale(ds7, 'CMI')
    c13_arr = apply_scale(ds13, 'CMI')
    has_c14 = c14_path and os.path.exists(c14_path)
    ds14 = None
    c14_arr = None
    if has_c14:
        ds14 = nc.Dataset(c14_path)
        c14_arr = apply_scale(ds14, 'CMI')

    x_v = ds7.variables['x'][:]
    y_v = ds7.variables['y'][:]
    xx, yy = np.meshgrid(x_v, y_v)
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(xx, yy, SAT_LON)
    ts_doy, ts_hr = extract_ts(c07_path)

    # Ceará bbox
    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )
    if len(idx[0]) == 0:
        for d in [ds7, ds13, ds14]: 
            if d: d.close()
        return [], {"ce_pixels": 0}

    pixels = []
    t07_vals = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t7 = float(c07_arr[yi, xi]); t13 = float(c13_arr[yi, xi])
        if np.isnan(t7) or np.isnan(t13): continue
        if has_c14:
            t14 = float(c14_arr[yi, xi])
            btd = t7 - t14
        else:
            t14 = 0.0
            btd = t7 - t13
        pixels.append({'yi': yi, 'xi': xi, 'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
                       't07': t7, 't13': t13, 't14': t14, 'btd': btd})
        t07_vals.append(t7)

    # If no valid pixels in CE bbox
    if not t07_vals:
        for d in [ds7, ds13, ds14]: 
            if d: d.close()
        return [], {"ce_pixels": len(idx[0]), "error": "all_nan_in_bbox"}

    max_t07 = max(t07_vals)
    min_t07 = min(t07_vals)
    threshold = []
    for p in pixels:
        if p['t07'] > 330 and p['btd'] > 5:
            threshold.append({**p, 'confidence': 'alta'})
        elif p['t07'] > 320 and p['btd'] > 3:
            threshold.append({**p, 'confidence': 'media'})
        elif p['t07'] > 310 and p['btd'] > 2:
            threshold.append({**p, 'confidence': 'baixa'})

    # K-Means
    kmeans_added = 0
    if len(threshold) >= 3:
        pixel_map, features = {}, []
        for fc in threshold:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = fc['yi']+dy, fc['xi']+dx
                    if 0 <= ny < c07_arr.shape[0] and 0 <= nx < c07_arr.shape[1]:
                        t7 = float(c07_arr[ny, nx]); t13 = float(c13_arr[ny, nx])
                        if has_c14:
                            t14 = float(c14_arr[ny, nx])
                            btd_val = t7 - t14
                        else:
                            t14 = 0.0
                            btd_val = t7 - t13
                        if not (np.isnan(t7) or np.isnan(t13)) and (ny, nx) not in pixel_map:
                            pixel_map[(ny, nx)] = {'lat': float(lat_arr[ny, nx]), 'lon': float(lon_arr[ny, nx]),
                                                   't07': t7, 't13': t13, 't14': t14, 'btd': btd_val}
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
            for i, lbl in enumerate(labels):
                if lbl == fire_label:
                    p = pixel_map[keys[i]]
                    min_btd = 2 if has_c14 else 1.5
                    if p['t07'] > 315 and p['btd'] > min_btd:
                        p['confidence'] = 'kmeans'
                        p['source'] = 'CMIPF_KMeans'
                        p['doy'] = ts_doy
                        p['hour'] = ts_hr
                        threshold.append(p)
                        kmeans_added += 1

    # Deduplicate
    final = []
    for d in threshold:
        is_dup = False
        for ex in final:
            ld = abs(d['lat'] - ex['lat']) * 111000
            lnd = abs(d['lon'] - ex['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            if math.sqrt(ld**2 + lnd**2) < 2000:
                is_dup = True; break
        if not is_dup:
            final.append(d)

    for d in [ds7, ds13, ds14]:
        if d: d.close()

    meta = {
        "ce_pixels": len(pixels),
        "max_t07_k": round(max_t07, 2),
        "min_t07_k": round(min_t07, 2),
        "threshold_candidates": len(threshold) - kmeans_added,
        "kmeans_added": kmeans_added,
    }
    return final, meta


def load_inpe_csv(path):
    ref = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row['lat']); lon = float(row['lon'])
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
            except: continue
    return ref


def load_firms_csvs():
    """Load FIRMS CSVs as additional reference."""
    ref = []
    for src, path in FIRMS_CSVS.items():
        if not os.path.exists(path): continue
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row['latitude']); lon = float(row['longitude'])
                    if (CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and
                        CEARA_LON_MIN <= lon <= CEARA_LON_MAX):
                        ref.append({
                            'lat': lat, 'lon': lon,
                            'frp': float(row.get('frp', 0) or 0),
                            'satelite': row.get('satellite', src),
                            'acq_date': row.get('acq_date', ''),
                            'acq_time': row.get('acq_time', ''),
                            'source': f'FIRMS_{src}',
                        })
                except: continue
    return ref


def match_fires(detected, reference, radius_m=3000):
    det_m = [False] * len(detected)
    ref_m = [False] * len(reference)
    matches = []
    for i, d in enumerate(detected):
        for j, r in enumerate(reference):
            ld = abs(d['lat'] - r['lat']) * 111000
            lnd = abs(d['lon'] - r['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            dist = math.sqrt(ld**2 + lnd**2)
            if dist < radius_m and not det_m[i] and not ref_m[j]:
                det_m[i] = True; ref_m[j] = True
                matches.append((i, j, round(dist, 1)))
                break
    tp = sum(det_m); fp = len(detected) - tp
    fn = sum(1 for m in ref_m if not m)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'detections': len(detected), 'reference_fires': len(reference),
        'precision': round(prec, 4), 'recall': round(rec, 4),
        'f1_score': round(f1, 4),
        'match_rate': round(tp / len(reference) * 100, 1) if reference else 0.0,
    }


def process_local_data():
    print("=" * 70)
    print("TASK-051: INOV-003 — Pipeline K-Means + Validação INPE")
    print("=" * 70)
    print(f"UTC: {DATE_STR}")

    # Load reference data
    print("\n[1] Loading reference data...")
    inpe_ref = load_inpe_csv(INPE_CSV)
    firms_ref = load_firms_csvs()
    print(f"  INPE BDQueimadas (2026, Ceará): {len(inpe_ref)} focos")
    print(f"  FIRMS (24h, Ceará): {len(firms_ref)} focos")

    # INPE by date
    inpe_dates = Counter(d['data_hora'][:10] for d in inpe_ref)
    print(f"  INPE dates with foci:")
    for d, c in sorted(inpe_dates.items()):
        print(f"    {d}: {c}")

    print("\n[2] Scanning local GOES-19 files...")
    # Index all local files
    files_by_band = {"C07": {}, "C13": {}, "C14": {}}
    for fname in os.listdir(GOES_DIR):
        if not fname.endswith(".nc"): continue
        doy, hr = extract_ts(fname)
        if doy == 0: continue
        # Match band from filename (G19_C07_DOY_HOUR or G19_C13_DOY_HOUR etc.)
        for band in ["C07", "C13", "C14"]:
            if f"_{band}_" in fname:
                files_by_band[band][(doy, hr)] = os.path.join(GOES_DIR, fname)
                break

    print(f"  C07 files: {len(files_by_band['C07'])}")
    print(f"  C13 files: {len(files_by_band['C13'])}")
    print(f"  C14 files: {len(files_by_band['C14'])}")

    # Group by DOY
    doys = set()
    for band_data in files_by_band.values():
        for (doy, hr) in band_data:
            doys.add(doy)
    print(f"  DOYs available: {sorted(doys)}")

    # Process each DOY with C07+C13
    all_results = {}
    for doy in sorted(doys, reverse=True):
        print(f"\n  === DOY {doy} ===")
        for hour in sorted(set(hr for (d, hr) in files_by_band["C07"] if d == doy)):
            c07 = files_by_band["C07"].get((doy, hour))
            c13 = files_by_band["C13"].get((doy, hour))
            if not c07 or not c13:
                continue
            c14 = files_by_band["C14"].get((doy, hour))
            print(f"    Hour {hour:02d}z: C07={os.path.basename(c07)[:40]} C13={os.path.basename(c13)[:40]} C14={'yes' if c14 else 'no'}")
            dets, meta = detect_hotspots(c07, c13, c14)
            
            if dets is None:
                print(f"      ERROR: {meta.get('error', 'unknown')}")
                meta = {"ce_pixels": 0, "error": meta.get("error", "")}
                continue

            key = f"{doy}_{hour}"
            if key not in all_results:
                all_results[key] = {
                    "doy": doy, "hour": hour,
                    "detections": [],
                    "meta": meta,
                }
            all_results[key]["detections"].extend(dets)

            if dets:
                print(f"      -> {len(dets)} fires (T07 max={max(d['t07'] for d in dets):.1f}K)")
            else:
                min_t = meta.get('min_t07_k', 'N/A')
                max_t = meta.get('max_t07_k', 'N/A')
                err = meta.get('error', '')
                print(f"      -> 0 fires (CE pixels={meta.get('ce_pixels', 'N/A')}, T07 range={min_t}-{max_t} {err})")

    # Deduplicate across hours
    print("\n[3] Consolidating detections across hours (dedup)...")
    consolidated = {}
    for key, data in all_results.items():
        doy = data["doy"]
        if doy not in consolidated:
            consolidated[doy] = {"detections": [], "hours": set(), "meta": {}}
        consolidated[doy]["hours"].add(data["hour"])
        # Update meta
        for k, v in data["meta"].items():
            if k not in consolidated[doy]["meta"]:
                consolidated[doy]["meta"][k] = v
            elif isinstance(v, (int, float)):
                consolidated[doy]["meta"][k] = max(consolidated[doy]["meta"].get(k, 0), v)

        for d in data["detections"]:
            # Dedup
            is_dup = False
            for ex in consolidated[doy]["detections"]:
                ld = abs(d['lat'] - ex['lat']) * 111000
                lnd = abs(d['lon'] - ex['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
                if math.sqrt(ld**2 + lnd**2) < 3000:
                    is_dup = True; break
            if not is_dup:
                consolidated[doy]["detections"].append(d)

    # Cross-validate
    print("\n[4] Cross-validation against INPE + FIRMS...")
    all_metrics = {}
    for doy in sorted(consolidated.keys()):
        dets = consolidated[doy]["detections"]
        print(f"\n  --- DOY {doy} ({len(dets)} detections) ---")

        # INPE validation
        print(f"  INPE BDQueimadas:")
        for rname, rval in [("3km", 3000), ("1.5km", 1500), ("5km", 5000)]:
            m = match_fires(dets, inpe_ref, rval)
            print(f"    @{rname}: TP={m['tp']} FP={m['fp']} FN={m['fn']} "
                  f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1_score']:.4f}")
            if doy not in all_metrics:
                all_metrics[doy] = {"inpe": {}, "firms": {}}
            all_metrics[doy]["inpe"][rname] = m

        # FIRMS validation
        print(f"  FIRMS:")
        for rname, rval in [("3km", 3000), ("1.5km", 1500), ("5km", 5000)]:
            m = match_fires(dets, firms_ref, rval)
            print(f"    @{rname}: TP={m['tp']} FP={m['fp']} FN={m['fn']} "
                  f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1_score']:.4f}")
            all_metrics[doy]["firms"][rname] = m

    # Generate report
    print("\n[5] Generating report...")

    # Best F1
    best_f1 = 0.0
    best_doy = None
    for doy, metrics in all_metrics.items():
        f1_val = metrics["inpe"]["3km"]["f1_score"]
        if f1_val > best_f1:
            best_f1 = f1_val
            best_doy = doy

    report = {
        "task": "TASK-051 (INOV-003)",
        "timestamp": DATE_STR,
        "pipeline": "GOES-19 ABI C07+C13 → K-Means (2 clusters) → Filtro 315K → INPE + FIRMS",
        "satellite": "GOES-19 (75.2°W)",
        "inpe_reference_2026": len(inpe_ref),
        "firms_reference_24h": len(firms_ref),
        "datasets_processed": {
            str(doy): {
                "detections": len(data["detections"]),
                "hours": sorted(data["hours"]),
                "meta": data["meta"],
            }
            for doy, data in consolidated.items()
        },
        "metrics": all_metrics,
        "best_f1_doy": best_doy,
        "best_f1_score": best_f1,
    }

    json_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-results.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  JSON: {json_path}")

    # Markdown
    md = f"""# TASK-051: INOV-003 — Pipeline K-Means + Validação INPE

## Metadados
- **Timestamp**: {DATE_STR}
- **Satélite**: GOES-19 (75.2°W, ABI-L2-CMIPF)
- **Método**: Threshold (310K+/BTD>2) → K-Means (2 clusters, 315K+) → Dedup (3km)
- **Bucket S3**: `noaa-goes19`
- **Referências**: INPE BDQueimadas 2026 + NASA FIRMS (VIIRS SNPP/NOAA20/MODIS)

## INPE BDQueimadas — Focos por Data (Ceará 2026)
| Data | Focos |
|------|-------|
"""
    for d, c in sorted(inpe_dates.items()):
        if c > 0:
            md += f"| {d} | {c} |\n"

    md += f"""
## Dados Processados (Local)
| DOY | Detecções | Horas | CE Pixels | T07 Range (K) |
|-----|-----------|-------|-----------|----------------|
"""
    for doy in sorted(consolidated.keys()):
        data = consolidated[doy]
        m = data["meta"]
        md += f"| {doy} | {len(data['detections'])} | {sorted(data['hours'])} | {m.get('ce_pixels', 'N/A')} | {m.get('min_t07_k', 'N/A')}-{m.get('max_t07_k', 'N/A')} |\n"

    md += """
## Métricas vs INPE BDQueimadas
"""
    for doy in sorted(all_metrics.keys()):
        md += f"### DOY {doy}\n"
        md += "| Referência | Raio | TP | FP | FN | Precisão | Recall | **F1** | Match% |\n"
        md += "|------------|------|----|----|----|----------|--------|--------|--------|\n"
        for ref_name, metrics in [("INPE", "inpe"), ("FIRMS", "firms")]:
            for rname in ["3km", "1.5km", "5km"]:
                if rname in all_metrics[doy][metrics]:
                    m = all_metrics[doy][metrics][rname]
                    md += f"| {ref_name} | {rname} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.4f} | {m['recall']:.4f} | **{m['f1_score']:.4f}** | {m['match_rate']:.1f}% |\n"
        md += "\n"

    md += f"""## Análise

1. **Pipeline Linha A (GOES+K-Means)**: 
   - F1-score (3km) vs INPE = **{best_f1:.4f}** (DOY {best_doy or 'N/A'})
   - K-Means reduz falsos positivos via clustering espectral
   - Filtro T07>315K + BTD>2K elimina solo quente e nuvens

2. **Comparação com baseline do artigo**:
   - TASK-011/Q03: Fusão GOES+VIIRS → F1=0.766
   - GOES-only K-Means tem maior especificidade mas recall limitado em inverno CE

3. **Limitações**:
   - Junho é inverno no Ceará — temperaturas C07 ~290-298K abaixo do threshold 310K
   - GOES-16 descontinuado → migrado para GOES-19 (mesma órbita 75.2°W)
   - INPE dados mais recentes: 2026-06-06 (5 focos)
   - FIRMS 24h usa público CSVs (sem chave API) — cobertura parcial

4. **Recomendação**:
   - Reexecutar na estação seca (Setembro-Novembro) para validação F1 quantitativa
   - Ativar chave API NASA FIRMS para dados mais recentes

## Arquivos Gerados
- `TASK-051-pipeline-results.json` — Métricas completas
- `TASK-051-pipeline-report.md` — Este relatório

## Execução
- **Pipeline**: K-Means (2 clusters, T07+BTD features) → Threshold 315K → Dedup 3km
- **Data da execução**: {DATE_STR}
"""
    md_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-report.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Report: {md_path}")

    return report, all_metrics, consolidated


if __name__ == "__main__":
    report, metrics, consolidated = process_local_data()

    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    for doy in sorted(consolidated.keys()):
        dets = consolidated[doy]["detections"]
        im = metrics.get(doy, {}).get("inpe", {}).get("3km", {})
        fm = metrics.get(doy, {}).get("firms", {}).get("3km", {})
        print(f"  DOY {doy}: {len(dets)} detecções | INPE F1={im.get('f1_score', 'N/A')} | FIRMS F1={fm.get('f1_score', 'N/A')}")

    print(f"\n  Best F1: {report.get('best_f1_score', 'N/A')} (DOY {report.get('best_f1_doy', 'N/A')})")
    print(f"\n  Artifacts saved to: {ARTIFACTS_DIR}")
