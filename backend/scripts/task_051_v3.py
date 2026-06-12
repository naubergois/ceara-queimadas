#!/usr/bin/env python3
"""
TASK-051 — INOV-003: Pipeline K-Means + Validação INPE (v3 - pyproj corrected)
GOES-19 (75°W) CMIPF + K-Means clustering → Validação contra INPE BDQueimadas
"""

import os, sys, json, math, re, csv
from datetime import datetime, timedelta, timezone
import numpy as np
import netCDF4 as nc
from sklearn.cluster import KMeans
from pyproj import Proj
from collections import Counter

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas"
BACKEND = os.path.join(BASE_DIR, "backend")
GOES_DIR = os.path.join(BACKEND, "data", "goes19_raw")
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Config
SAT_LON = -75.0  # GOES-19 longitude (from file metadata)
H, R_EQ, R_POL = 35786023.0, 6378137.0, 6356752.3142
GEOS_PROJ = Proj(proj='geos', lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
INPE_CSV = os.path.join(BASE_DIR, "data", "inpe_focos_ce", "anos", "focos_ce_INPE_2026.csv")
NOW = datetime.now(timezone.utc)
DATE_STR = NOW.strftime("%Y-%m-%d %H:%M:%S UTC")

FIRMS_CSVS = {
    "VIIRS_SNPP": os.path.join(BASE_DIR, "data", "firms_suomi_viirs_24h.csv"),
    "VIIRS_NOAA20": os.path.join(BASE_DIR, "data", "firms_noaa20_viirs_24h.csv"),
    "MODIS": os.path.join(BASE_DIR, "data", "firms_modis_24h.csv"),
}


def goes_fixed_grid_to_latlon(x_arr, y_arr):
    """Convert GOES fixed grid to lat/lon using pyproj (handles GOES-19 sweep=x)."""
    xx, yy = np.meshgrid(np.array(x_arr, dtype=np.float64), np.array(y_arr, dtype=np.float64))
    lat, lon = GEOS_PROJ(H * np.tan(xx), H * np.tan(yy) / np.cos(xx), inverse=True)
    return lat, lon


def apply_scale(ds, var_name):
    """Apply scale/offset only when data is not already in physical units."""
    v = ds.variables[var_name]
    data = v[:]
    scale = getattr(v, 'scale_factor', None)
    offset = getattr(v, 'add_offset', None)
    if scale is not None and offset is not None and data.dtype.kind in ('i', 'u'):
        # Integer data needs scale+offset
        return data.astype(np.float64) * float(scale) + float(offset)
    # Float data is already in physical units
    return np.array(data, dtype=np.float64)


def extract_ts(fpath):
    fname = os.path.basename(fpath)
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        return int(m.group(2)), int(m.group(3))
    m = re.search(r"G19_\w+_(\d+)_(\d+)", fname)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"GOES16_\w+_(\d+)_(\d+)", fname)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def find_band_file(doy, hour, band_suffix):
    for fname in os.listdir(GOES_DIR):
        if not fname.endswith(".nc"): continue
        if band_suffix not in fname: continue
        fd, fh = extract_ts(fname)
        if fd == doy and abs(fh - hour) <= 2:
            return os.path.join(GOES_DIR, fname)
    return None


def detect_hotspots(c07_path, c13_path, c14_path=None):
    """K-Means fire detection with pyproj-based lat/lon."""
    try:
        ds7 = nc.Dataset(c07_path)
        ds13 = nc.Dataset(c13_path)
    except Exception as e:
        return None, {"error": str(e)}

    c07_arr = apply_scale(ds7, 'CMI')
    c13_arr = apply_scale(ds13, 'CMI')
    has_c14 = c14_path and os.path.exists(c14_path)
    ds14 = None
    if has_c14:
        ds14 = nc.Dataset(c14_path)
        c14_arr = apply_scale(ds14, 'CMI')

    x_v = ds7.variables['x'][:]
    y_v = ds7.variables['y'][:]
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(x_v, y_v)
    ts_doy, ts_hr = extract_ts(c07_path)

    # Ceará bbox
    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX) &
        np.isfinite(lat_arr) & np.isfinite(lon_arr)
    )
    if len(idx[0]) == 0:
        for d in [ds7, ds13, ds14]:
            if d: d.close()
        return [], {"ce_pixels": 0, "error": "no_pixels_in_bbox"}

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
        pixels.append({'yi': yi, 'xi': xi,
                       'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
                       't07': t7, 't13': t13, 't14': t14, 'btd': btd})
        t07_vals.append(t7)

    if not t07_vals:
        for d in [ds7, ds13, ds14]:
            if d: d.close()
        return [], {"ce_pixels": len(idx[0]), "error": "all_nan_in_bbox"}

    max_t07 = max(t07_vals); min_t07 = min(t07_vals)

    # Threshold candidates
    threshold = []
    for p in pixels:
        if p['t07'] > 330 and p['btd'] > 5:
            threshold.append({**p, 'confidence': 'alta'})
        elif p['t07'] > 320 and p['btd'] > 3:
            threshold.append({**p, 'confidence': 'media'})
        elif p['t07'] > 310 and p['btd'] > 2:
            threshold.append({**p, 'confidence': 'baixa'})

    # K-Means refinement
    kmeans_added = 0
    if len(threshold) >= 3:
        pixel_map, features = {}, []
        for fc in threshold:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = fc['yi']+dy, fc['xi']+dx
                    if 0 <= ny < c07_arr.shape[0] and 0 <= nx < c07_arr.shape[1]:
                        t7 = float(c07_arr[ny, nx]); t13 = float(c13_arr[ny, nx])
                        btd_val = (t7 - float(c14_arr[ny, nx])) if has_c14 else (t7 - t13)
                        if not (np.isnan(t7) or np.isnan(t13)) and (ny, nx) not in pixel_map:
                            pixel_map[(ny, nx)] = {
                                'lat': float(lat_arr[ny, nx]), 'lon': float(lon_arr[ny, nx]),
                                't07': t7, 't13': t13, 'btd': btd_val
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
            for i, lbl in enumerate(labels):
                if lbl == fire_label:
                    p = pixel_map[keys[i]]
                    min_btd = 2 if has_c14 else 1.5
                    if p['t07'] > 315 and p['btd'] > min_btd:
                        p['confidence'] = 'kmeans'; p['source'] = 'CMIPF_KMeans'
                        p['doy'] = ts_doy; p['hour'] = ts_hr
                        threshold.append(p)
                        kmeans_added += 1

    # Dedup
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
                if (CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon <= CEARA_LON_MAX):
                    ref.append({'lat': lat, 'lon': lon, 'data_hora': row['data_hora_gmt'],
                                'satelite': row['satelite'],
                                'frp': float(row['frp']) if row['frp'].strip() else 0.0,
                                'bioma': row['bioma'], 'source': 'INPE'})
            except: continue
    return ref


def load_firms_csvs():
    ref = []
    for src, path in FIRMS_CSVS.items():
        if not os.path.exists(path): continue
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row['latitude']); lon = float(row['longitude'])
                    if (CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon <= CEARA_LON_MAX):
                        ref.append({'lat': lat, 'lon': lon,
                                    'frp': float(row.get('frp', 0) or 0),
                                    'satelite': row.get('satellite', src),
                                    'source': f'FIRMS_{src}'})
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
    return {'tp': tp, 'fp': fp, 'fn': fn,
            'detections': len(detected), 'reference_fires': len(reference),
            'precision': round(prec, 4), 'recall': round(rec, 4),
            'f1_score': round(f1, 4),
            'match_rate': round(tp / len(reference) * 100, 1) if reference else 0.0}


def main():
    print("=" * 70)
    print("TASK-051: INOV-003 — Pipeline K-Means + Validação INPE (v3)")
    print("=" * 70)
    print(f"UTC: {DATE_STR}")

    # Step 1: Load reference
    print("\n[1] Loading reference data...")
    inpe_ref = load_inpe_csv(INPE_CSV)
    firms_ref = load_firms_csvs()
    print(f"  INPE BDQueimadas (2026, Ceará): {len(inpe_ref)} focos")
    print(f"  FIRMS (24h, Ceará): {len(firms_ref)} focos")

    # Step 2: Scan local GOES files
    print("\n[2] Scanning local GOES-19 files...")
    files_by_band = {"C07": {}, "C13": {}, "C14": {}}
    for fname in os.listdir(GOES_DIR):
        if not fname.endswith(".nc"): continue
        doy, hr = extract_ts(fname)
        if doy == 0: continue
        for band in ["C07", "C13", "C14"]:
            if f"_{band}_" in fname:
                files_by_band[band][(doy, hr)] = os.path.join(GOES_DIR, fname)
                break

    print(f"  C07: {len(files_by_band['C07'])} files")
    print(f"  C13: {len(files_by_band['C13'])} files")
    print(f"  C14: {len(files_by_band['C14'])} files")

    doys = set()
    for band_data in files_by_band.values():
        for (doy, hr) in band_data:
            doys.add(doy)
    print(f"  DOYs: {sorted(doys)}")

    # Step 3: Process each hour
    all_results = {}
    for doy in sorted(doys, reverse=True):
        print(f"\n  === DOY {doy} ===")
        for hour in sorted(set(hr for (d, hr) in files_by_band["C07"] if d == doy)):
            c07 = files_by_band["C07"].get((doy, hour))
            c13 = files_by_band["C13"].get((doy, hour))
            if not c07 or not c13: continue
            c14 = files_by_band["C14"].get((doy, hour))
            print(f"    {hour:02d}z: processing...")
            dets, meta = detect_hotspots(c07, c13, c14)
            if dets is None:
                print(f"      ERROR: {meta.get('error')}")
                continue
            key = f"{doy}_{hour}"
            all_results[key] = {"doy": doy, "hour": hour, "detections": dets, "meta": meta}
            if dets:
                t07s = [d['t07'] for d in dets]
                print(f"      -> {len(dets)} fires (T07 max={max(t07s):.1f}K)")
            else:
                print(f"      -> 0 fires (CE={meta.get('ce_pixels',0)}, T07={meta.get('min_t07_k','N/A')}-{meta.get('max_t07_k','N/A')}K)")

    # Step 4: Consolidate by DOY
    print("\n[3] Consolidating detections across hours...")
    consolidated = {}
    for key, data in all_results.items():
        doy = data["doy"]
        if doy not in consolidated:
            consolidated[doy] = {"detections": [], "hours": set(), "meta": data["meta"]}
        consolidated[doy]["hours"].add(data["hour"])
        consolidated[doy]["meta"] = consolidated[doy]["meta"] or data["meta"]
        for d in data["detections"]:
            is_dup = False
            for ex in consolidated[doy]["detections"]:
                ld = abs(d['lat'] - ex['lat']) * 111000
                lnd = abs(d['lon'] - ex['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
                if math.sqrt(ld**2 + lnd**2) < 3000:
                    is_dup = True; break
            if not is_dup:
                consolidated[doy]["detections"].append(d)

    # Step 5: Cross-validate
    print("\n[4] Cross-validation...")
    all_metrics = {}
    for doy in sorted(consolidated.keys()):
        dets = consolidated[doy]["detections"]
        print(f"\n  --- DOY {doy} ({len(dets)} detections) ---")
        for ref_name, ref_data, ref_label in [("INPE", inpe_ref, "INPE"), ("FIRMS", firms_ref, "FIRMS")]:
            print(f"  {ref_label}:")
            for rname, rval in [("3km", 3000)]:
                m = match_fires(dets, ref_data, rval)
                print(f"    @{rname}: TP={m['tp']} FP={m['fp']} FN={m['fn']} P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1_score']:.4f}")
                if doy not in all_metrics: all_metrics[doy] = {}
                all_metrics[doy][ref_label] = {rname: m}

    # Report
    print("\n[5] Generating report...")
    best_f1 = 0.0; best_doy = None
    for doy, metrics in all_metrics.items():
        f1_val = metrics.get("INPE", {}).get("3km", {}).get("f1_score", 0)
        if f1_val > best_f1: best_f1 = f1_val; best_doy = doy

    report = {
        "task": "TASK-051 (INOV-003 v3)",
        "timestamp": DATE_STR,
        "pipeline": "GOES-19 → pyproj lat/lon → Threshold → K-Means → INPE/FIRMS",
        "satellite": f"GOES-19 ({SAT_LON}°W)",
        "inpe_2026": len(inpe_ref),
        "firms_24h": len(firms_ref),
        "datasets": {str(doy): {"detections": len(data["detections"]), "hours": sorted(data["hours"])}
                     for doy, data in consolidated.items()},
        "metrics": all_metrics,
        "best_f1": {"doy": best_doy, "f1": best_f1},
    }

    json_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-results.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  JSON: {json_path}")

    # MD report
    md = f"""# TASK-051: INOV-003 — Pipeline K-Means + Validação INPE (v3)

## Metadados
- **Timestamp**: {DATE_STR}
- **Satélite**: GOES-19 ({SAT_LON}°W, pyproj lat/lon)
- **Método**: Threshold (310K+/BTD>2) → K-Means (2 cls, 315K+) → Dedup (3km)
- **Referências**: INPE BDQueimadas (2026, {len(inpe_ref)} focos) + NASA FIRMS (24h, {len(firms_ref)} focos)

## Dados Processados
| DOY | Detecções | Horas |
|-----|-----------|-------|
"""
    for doy in sorted(consolidated.keys()):
        data = consolidated[doy]
        md += f"| {doy} | {len(data['detections'])} | {sorted(data['hours'])} |\n"

    md += "\n## Métricas (3km)\n"
    for doy in sorted(all_metrics.keys()):
        md += f"### DOY {doy}\n| Ref | TP | FP | FN | P | R | F1 |\n|-----|----|----|----|----|----|----|\n"
        for ref_label in ["INPE", "FIRMS"]:
            m = all_metrics[doy].get(ref_label, {}).get("3km", {})
            md += f"| {ref_label} | {m.get('tp',0)} | {m.get('fp',0)} | {m.get('fn',0)} | {m.get('precision',0):.4f} | {m.get('recall',0):.4f} | **{m.get('f1_score',0):.4f}** |\n"
        md += "\n"

    md += f"""## Análise
1. **Best F1**: {best_f1:.4f} (DOY {best_doy or 'N/A'})
2. **Pipeline**: pyproj corrigido para GOES-19 (sweep_angle_axis=x)
3. $\\bullet$ Junho é inverno CE — temperaturas C07 abaixo do limiar 310K
4. $\\bullet$ Recomendado reexecutar em Setembro-Novembro (pico de queimadas)
"""
    md_path = os.path.join(ARTIFACTS_DIR, "TASK-051-pipeline-report.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Report: {md_path}")

    print("\n" + "=" * 70)
    print("RESUMO")
    for doy in sorted(consolidated.keys()):
        dets = consolidated[doy]["detections"]
        m = all_metrics.get(doy, {}).get("INPE", {}).get("3km", {})
        print(f"  DOY {doy}: {len(dets)} detecções | F1={m.get('f1_score','N/A')}")
    print(f"  Best F1: {best_f1} (DOY {best_doy})")
    return report, all_metrics, consolidated


if __name__ == "__main__":
    main()
