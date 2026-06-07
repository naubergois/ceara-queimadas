#!/usr/bin/env python3
"""Cron job runner for June 6, 2026 — finds latest C07+C13 pairs, runs analysis."""
import os, sys, json, math, re, traceback
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import netCDF4 as nc
import numpy as np

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.expanduser("~/sistemasatelitefunceme")
OUTPUT_DIR = "/Users/naubergois/.hermes/profiles/analista-queimadas/cron/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
GOES16_LON = -75.2
GOES18_LON = -137.2

def report(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def extract_timestamp(filepath):
    fname = os.path.basename(filepath)
    # Standard: _sYYYYDOYHHMMSS
    match = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if match:
        year, doy, hour, minute, second = match.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(
            days=int(doy)-1, hours=int(hour), minutes=int(minute), seconds=int(second))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    # Legacy: GOES19_C07_DOY_HH
    match = re.search(r"GOES1[89]_\w+_(\d{3})_(\d{2})\.nc", fname)
    if match:
        doy, hour = match.groups()
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hour))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a = 6378137.0; b = 6356752.31414; h = 35786023.0
    lambda_0 = math.radians(sat_lon_deg)
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)
    cos_x = np.cos(x_rad); sin_x = np.sin(x_rad)
    cos_y = np.cos(y_rad); sin_y = np.sin(y_rad)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    B = -2.0*h*cos_x*cos_y
    c_term = h_sq - a_sq
    discriminant = B*B - 4*a_term*c_term
    sd = np.sqrt(np.maximum(discriminant, 0))
    s_d = (-B - sd)/(2*a_term)
    lat = np.degrees(np.arctan2(
        -cos_x * sin_y,
        np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq) * sin_x**2 * sin_y**2, 0))))
    lon = np.degrees(lambda_0 + np.arctan2(s_d * sin_x * cos_y, h - s_d * cos_x * cos_y))
    return lat, lon

def extract_goes_projection(ds, default_lon):
    sat_lon = default_lon
    proj = ds.variables.get('goes_imager_projection')
    if proj is not None:
        try: sat_lon = float(getattr(proj, 'longitude_of_projection_origin'))
        except: pass
    if 'nominal_satellite_subpoint_lon' in ds.variables:
        try:
            val = ds.variables['nominal_satellite_subpoint_lon'][:]
            if isinstance(val, np.ndarray) and val.size > 0:
                sat_lon = float(val.flat[0])
        except: pass
    return sat_lon

def apply_scale_and_offset(ds, var_name):
    var = ds.variables[var_name]
    data = var[:]
    raw_is_int = data.dtype.kind in ('i', 'u')
    if raw_is_int:
        scale = getattr(var, 'scale_factor', 1.0)
        offset = getattr(var, 'add_offset', 0.0)
        return data.astype(np.float64) * scale + offset
    return data.astype(np.float64)

def find_latest_pairs():
    """Find latest C07+C13 pairs from any naming convention."""
    files = os.listdir(DATA_DIR)
    result = {}

    # --- Standard GOES naming: OR_ABI-L2-CMIPF-M6C07_G19_s20261570800216... ---
    goes19_standard = defaultdict(lambda: {'c07': None, 'c13': None})
    for f in files:
        m = re.search(r'C0?(\d+)_G19_s(\d{4})(\d{3})(\d{2})', f)
        if m:
            band = int(m.group(1))
            ts_key = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"  # year-doy-hour
            fpath = os.path.join(DATA_DIR, f)
            if band == 7:
                goes19_standard[ts_key]['c07'] = fpath
            elif band == 13:
                goes19_standard[ts_key]['c13'] = fpath

    complete_std = {k: v for k, v in goes19_standard.items() if v['c07'] and v['c13']}
    if complete_std:
        latest_ts = sorted(complete_std.keys())[-1]
        l = complete_std[latest_ts]
        result['goes19_standard'] = {'c07': l['c07'], 'c13': l['c13'], 'ts': latest_ts}

    # --- Legacy naming: GOES19_C07_DOY_HH.nc ---
    goes19 = {}
    for f in files:
        if f.startswith("GOES19_C07_") and f.endswith(".nc"):
            ts = f.replace("GOES19_C07_", "").replace(".nc", "")
            if ts not in goes19: goes19[ts] = {}
            goes19[ts]['c07'] = os.path.join(DATA_DIR, f)
        if f.startswith("GOES19_C13_") and f.endswith(".nc"):
            ts = f.replace("GOES19_C13_", "").replace(".nc", "")
            if ts not in goes19: goes19[ts] = {}
            goes19[ts]['c13'] = os.path.join(DATA_DIR, f)

    complete_legacy = {ts: v for ts, v in goes19.items() if 'c07' in v and 'c13' in v and 'test' not in ts}
    if complete_legacy:
        latest_ts = sorted(complete_legacy.keys())[-1]
        l = complete_legacy[latest_ts]
        result['goes19_legacy'] = {'c07': l['c07'], 'c13': l['c13'], 'ts': latest_ts}

    # --- GOES-18 ---
    goes18 = {}
    for f in files:
        if f.startswith("GOES18_C07_") and f.endswith(".nc"):
            ts = f.replace("GOES18_C07_", "").replace(".nc", "")
            if ts not in goes18: goes18[ts] = {}
            goes18[ts]['c07'] = os.path.join(DATA_DIR, f)
        if f.startswith("GOES18_C13_") and f.endswith(".nc"):
            ts = f.replace("GOES18_C13_", "").replace(".nc", "")
            if ts not in goes18: goes18[ts] = {}
            goes18[ts]['c13'] = os.path.join(DATA_DIR, f)

    complete_18 = {ts: v for ts, v in goes18.items() if 'c07' in v and 'c13' in v and 'test' not in ts}
    if complete_18:
        latest_ts = sorted(complete_18.keys())[-1]
        l = complete_18[latest_ts]
        result['goes18'] = {'c07': l['c07'], 'c13': l['c13'], 'ts': latest_ts}

    # Cache GOES-16
    b07 = os.path.join(CACHE_DIR, "b07.nc")
    b13 = os.path.join(CACHE_DIR, "b13.nc")
    if os.path.exists(b07) and os.path.exists(b13):
        result['goes16_cache'] = {'c07': b07, 'c13': b13}

    report(f"Pairs encontrados: {len(result)}")
    for k, v in result.items():
        if k == 'goes16_cache':
            report(f"  {k}: cache files")
        else:
            report(f"  {k}: {os.path.basename(v['c07'])} / {os.path.basename(v['c13'])} (ts={v.get('ts','?')})")
    return result

def process_goes_data(c07_path, c13_path, label, sat_lon):
    report(f"Processando {label}: {os.path.basename(c07_path)}")
    try:
        ds7 = nc.Dataset(c07_path)
        ds13 = nc.Dataset(c13_path)
    except Exception as e:
        report(f"  Erro abrindo datasets: {e}")
        return None

    try:
        x_var = ds7.variables['x']
        y_var = ds7.variables['y']
        actual_sat_lon = extract_goes_projection(ds7, sat_lon)
        if abs(actual_sat_lon - sat_lon) > 1:
            report(f"  Satélite detectado em {actual_sat_lon}° (assumido {sat_lon}°)")
            sat_lon = actual_sat_lon

        lat_arr, lon_arr = goes_fixed_grid_to_latlon(
            np.meshgrid(x_var[:], y_var[:])[0],
            np.meshgrid(x_var[:], y_var[:])[1],
            sat_lon)
        c07 = apply_scale_and_offset(ds7, 'CMI')
        c13 = apply_scale_and_offset(ds13, 'CMI')
        timestamp = extract_timestamp(c07_path)

        idx = np.where(
            (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
            (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX))
        pixels_ceara = len(idx[0])
        report(f"  Pixels em Ceará: {pixels_ceara}")

        if pixels_ceara == 0:
            return {
                "satellite": label, "sat_lon": sat_lon, "timestamp": timestamp,
                "cobre_ceara": False, "pixels_ceara": 0, "fire_pixels_count": 0, "hotspots": []}

        pixel_list = []
        for i in range(len(idx[0])):
            yi, xi = idx[0][i], idx[1][i]
            t07_v, t13_v = c07[yi, xi], c13[yi, xi]
            if np.ma.is_masked(t07_v) or np.ma.is_masked(t13_v): continue
            if math.isnan(float(t07_v)) or math.isnan(float(t13_v)): continue
            pixel_list.append({
                'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
                't07': float(t07_v), 't13': float(t13_v), 'btd': float(t07_v) - float(t13_v),
            })

        valid_pixels = len(pixel_list)
        report(f"  Pixels válidos: {valid_pixels}")
        if valid_pixels == 0:
            return {
                "satellite": label, "sat_lon": sat_lon, "timestamp": timestamp,
                "cobre_ceara": True, "pixels_ceara": 0, "valid_pixels": 0,
                "fire_pixels_count": 0, "hotspots": []}

        temps = [p['t07'] for p in pixel_list]
        btds = [p['btd'] for p in pixel_list]
        stats = {
            't07_min': round(min(temps), 1), 't07_max': round(max(temps), 1),
            't07_mean': round(np.mean(temps), 1), 't07_median': round(np.median(temps), 1),
            'btd_min': round(min(btds), 1), 'btd_max': round(max(btds), 1),
            'btd_mean': round(np.mean(btds), 1),
        }

        fire_315 = [p for p in pixel_list if p['t07'] >= 315 and p['btd'] > 2]
        fire_320 = [p for p in pixel_list if p['t07'] >= 320 and p['btd'] > 3]
        fire_330 = [p for p in pixel_list if p['t07'] >= 330 and p['btd'] > 5]

        report(f"  T07 range: {stats['t07_min']}K - {stats['t07_max']}K")
        report(f"  >=315K+B2K: {len(fire_315)} | >=320K+B3K: {len(fire_320)} | >=330K+B5K: {len(fire_330)}")

        from sklearn.cluster import KMeans

        n_for_kmeans = min(valid_pixels, 10000)
        if n_for_kmeans > 3000:
            indices = np.linspace(0, valid_pixels-1, 3000, dtype=int)
        else:
            indices = range(valid_pixels)

        sampled = [pixel_list[i] for i in indices]
        features = np.array([[p['t07'], p['t13'], p['btd']] for p in sampled])
        valid_idx = ~np.any(np.isnan(features), axis=1)
        features = features[valid_idx]
        sampled = [sampled[i] for i in range(len(sampled)) if valid_idx[i]]

        cluster_info = []
        fire_cluster_mean_t07 = 0

        if len(features) >= 10:
            f_mean = features.mean(axis=0); f_std = features.std(axis=0) + 1e-10
            features_norm = (features - f_mean) / f_std
            kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(features_norm)
            cluster_profiles = {}
            for i, label in enumerate(labels):
                if label not in cluster_profiles:
                    cluster_profiles[label] = {'t07': [], 'btd': [], 'count': 0}
                cluster_profiles[label]['t07'].append(features[i][0])
                cluster_profiles[label]['btd'].append(features[i][2])
                cluster_profiles[label]['count'] += 1
            for label, data in cluster_profiles.items():
                mean_t07 = np.mean(data['t07']); mean_btd = np.mean(data['btd'])
                cluster_info.append({
                    'cluster': int(label), 'count': data['count'],
                    'pct': round(data['count']/len(labels)*100, 1),
                    'mean_t07': round(float(mean_t07), 1),
                    'mean_btd': round(float(mean_btd), 1),
                    'is_fire': mean_t07 > 315 and mean_btd > 2})
            fire_cluster = max(cluster_profiles.keys(),
                key=lambda x: np.mean(cluster_profiles[x]['t07']))
            fire_cluster_mean_t07 = round(float(np.mean(cluster_profiles[fire_cluster]['t07'])), 1)

        cluster_info.sort(key=lambda c: c['mean_t07'], reverse=True)

        result = {
            "satellite": label, "sat_lon": sat_lon, "timestamp": timestamp,
            "cobre_ceara": True, "pixels_ceara": pixels_ceara,
            "valid_pixels": valid_pixels, "stats": stats,
            "hotspots_gte_315k": len(fire_315),
            "hotspots_gte_320k": len(fire_320),
            "hotspots_gte_330k": len(fire_330),
            "fire_pixels_count": len(fire_315),
            "kmeans_clusters": cluster_info,
            "fire_cluster_mean_t07": fire_cluster_mean_t07,
            "hotspots": [{"lat": round(p['lat'], 4), "lon": round(p['lon'], 4),
                          "t07": round(p['t07'], 1), "btd": round(p['btd'], 1)}
                         for p in sorted(fire_315, key=lambda x: x['t07'], reverse=True)[:20]],
        }
        return result
    finally:
        ds7.close(); ds13.close()

def read_previous_report():
    prev_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith("cron-") and f.endswith(".md")])
    if prev_files:
        with open(os.path.join(OUTPUT_DIR, prev_files[-1])) as f:
            return f.read()
    return ""

report("="*60)
report("INÍCIO — Análise de Queimadas (Cron Job)")
report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report("="*60)

pairs = find_latest_pairs()
results = {}

# Process standard GOES-19 naming first (newest data)
if 'goes19_standard' in pairs:
    r = process_goes_data(pairs['goes19_standard']['c07'], pairs['goes19_standard']['c13'],
                          "GOES-19 (standard)", GOES16_LON)
    if r: results['goes19_std'] = r

# Process legacy GOES-19 naming
if 'goes19_legacy' in pairs:
    r = process_goes_data(pairs['goes19_legacy']['c07'], pairs['goes19_legacy']['c13'],
                          "GOES-19 (legacy)", GOES16_LON)
    if r: results['goes19_leg'] = r

# GOES-18
if 'goes18' in pairs:
    r = process_goes_data(pairs['goes18']['c07'], pairs['goes18']['c13'],
                          "GOES-18", GOES18_LON)
    if r: results['goes18'] = r

# Cache GOES-16
if 'goes16_cache' in pairs:
    r = process_goes_data(pairs['goes16_cache']['c07'], pairs['goes16_cache']['c13'],
                          "GOES-16 (cache)", GOES16_LON)
    if r: results['goes16'] = r

# INPE reference data
results['inpe'] = {
    "ce_anual_2026": 601,
    "ce_rank_brasil": 8,
    "ce_ultimas_48h": 1,
    "brasil_48h": {"MT": 202, "TO": 68, "MA": 22, "MG": 20},
    "brasil_anual": {"MT": 1894, "BA": 1785, "PA": 1640, "RR": 1604, "TO": 1566, "MA": 1544},
}

# Read previous report for delta
prev = read_previous_report()
inpe_prev = None
for line in prev.split('\n'):
    m = re.search(r'Ceará.*Anual.*?\*\*(\d+) focos', line)
    if m: inpe_prev = int(m.group(1))

# Generate report
lines = []
lines.append("# 🛰️ Relatório de Queimadas — GOES + INPE")
lines.append(f"**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC-3")
lines.append("")

lines.append("## 🔥 INPE BDQueimadas — Situação Atual (05/06/2026)")
lines.append("")
lines.append("| Indicador | Valor |")
lines.append("|-----------|-------|")
lines.append(f"| Ceará — Anual 2026 | **{results['inpe']['ce_anual_2026']} focos** ({results['inpe']['ce_rank_brasil']}º no Brasil) |")
lines.append(f"| Ceará — Últimas 48h | **{results['inpe']['ce_ultimas_48h']} foco** |")
lines.append(f"| Brasil — Anual 2026 | **15.135 focos** |")
lines.append(f"| Brasil — Últimas 48h | MT={202}, TO={68}, MA={22}, MG={20} |")
lines.append("")
if inpe_prev:
    delta = results['inpe']['ce_anual_2026'] - inpe_prev
    sig = "+" if delta > 0 else ""
    lines.append(f"> 📊 **Δ INPE Ceará:** {inpe_prev} → {results['inpe']['ce_anual_2026']} ({sig}{delta})")
    lines.append("")

# GOES data sections
# Prefer standard naming (newest DOY 157 data) over legacy
sat_to_report = {}
if 'goes19_std' in results and results['goes19_std']:
    sat_to_report['GOES-19 (padrão)'] = results['goes19_std']
if 'goes19_leg' in results and results['goes19_leg']:
    sat_to_report['GOES-19 (legado)'] = results['goes19_leg']
if 'goes18' in results and results['goes18']:
    sat_to_report['GOES-18'] = results['goes18']
if 'goes16' in results and results['goes16']:
    sat_to_report['GOES-16 (cache)'] = results['goes16']

for sat_label, r in sat_to_report.items():
    lines.append(f"## 🛰️ {sat_label} — K-Means Fire Detection")
    lines.append("**Timestamp:** " + r['timestamp'])
    sat_pos = r.get('sat_lon', 0)
    is_east = abs(sat_pos + 75) < 5
    is_pacific = abs(sat_pos + 137) < 5
    if is_east:
        pos_str = f"{sat_pos:.1f}°W — GOES-East / Américas"
    elif is_pacific:
        pos_str = f"{sat_pos:.1f}°W — Pacífico"
    else:
        pos_str = f"{sat_pos}°W" if sat_pos else "?"
    lines.append(f"**Satélite:** {sat_label} ({pos_str})")
    lines.append(f"**Cobre Ceará:** {'✅ Sim' if r.get('cobre_ceara', True) else '❌ Não'} | **Pixels na região:** {r['pixels_ceara']}")
    lines.append("")

    if not r.get('cobre_ceara', True) or r['pixels_ceara'] == 0:
        sl = r.get('sat_lon', 0)
        lines.append(f"⚠️ O {sat_label} ({sl:.1f}°W) **não cobre o Ceará** neste scan. O satélite GOES-16 (75.2°W) é o que cobre o Brasil.")
        lines.append("")
        continue

    lines.append("| Métrica Termal | Valor |")
    lines.append("|-----------------|-------|")
    lines.append(f"| T07 (3.9µm) min | {r['stats']['t07_min']}K |")
    lines.append(f"| T07 (3.9µm) max | {r['stats']['t07_max']}K |")
    lines.append(f"| T07 (3.9µm) média | {r['stats']['t07_mean']}K |")
    lines.append(f"| T07 (3.9µm) mediana | {r['stats']['t07_median']}K |")
    lines.append(f"| BTD(7-13) min | {r['stats']['btd_min']}K |")
    lines.append(f"| BTD(7-13) max | {r['stats']['btd_max']}K |")
    lines.append(f"| BTD(7-13) média | {r['stats']['btd_mean']}K |")
    lines.append(f"| Pixels ≥ 315K + BTD>2K | **{r['hotspots_gte_315k']}** |")
    lines.append(f"| Pixels ≥ 320K + BTD>3K | **{r['hotspots_gte_320k']}** |")
    lines.append(f"| Pixels ≥ 330K + BTD>5K | **{r['hotspots_gte_330k']}** |")
    lines.append("")

    if r.get('kmeans_clusters'):
        lines.append("**Clusters K-Means (k=4):**")
        lines.append("")
        lines.append("| Cluster | % | T07 médio | BTD médio | Fogo? |")
        lines.append("|---------|---|-----------|-----------|-------|")
        for c in r['kmeans_clusters']:
            mark = "🔥" if c['is_fire'] else "🌲" if c['mean_t07'] < 300 else "⛅"
            lines.append(f"| {c['cluster']} | {c['pct']}% | {c['mean_t07']}K | {c['mean_btd']}K | {mark} |")
        lines.append("")

    if r.get('hotspots'):
        lines.append("**Hotspots detectados (top 20 por T07):**")
        lines.append("")
        lines.append("| Lat | Lon | T07 (3.9µm) | BTD(7-13) |")
        lines.append("|-----|-----|-------------|-----------|")
        for h in r['hotspots']:
            fire_icon = "🔥" if h['t07'] > 330 else "⚠️" if h['t07'] > 320 else "📍"
            lines.append(f"| {fire_icon} {h['lat']} | {h['lon']} | {h['t07']}K | {h['btd']}K |")
        lines.append("")

# Summary
total_fire = sum(
    r.get('fire_pixels_count', 0)
    for sat_label, r in sat_to_report.items() if r.get('cobre_ceara', True)
)

lines.append("## 📋 Resumo Executivo")
lines.append("")
lines.append(f"**INPE:** Ceará com **{results['inpe']['ce_anual_2026']} focos** acumulados em 2026 (8º no Brasil). Últimas 48h: 1 foco confirmado pelo satélite AQUA Tarde.")
lines.append("")

if total_fire > 0:
    lines.append(f"⚠️ **GOES detectou {total_fire} pixels candidate a fogo** nas bandas termais sobre o Ceará.")
else:
    lines.append("✅ **GOES não detectou pixels candidate a fogo** (>315K + BTD>2K) sobre o Ceará nos scans analisados.")
lines.append("")

# Processing notes
lines.append("### Observações do Pipeline")
lines.append("")

# Find the best GOES source with coverage
best_goes = None
for sat_label, r in sat_to_report.items():
    if r.get('pixels_ceara', 0) > 0:
        best_goes = (sat_label, r)
        break

if best_goes:
    sl, r = best_goes
    lines.append(f"- **{sl} ({r.get('sat_lon', 0):.1f}°W):** Scan mais recente processado: {r['timestamp']}.")
    lines.append(f"  - Pixels sobre Ceará: {r['pixels_ceara']} | Válidos: {r.get('valid_pixels', 0)}")
    lines.append(f"  - T07 médio: {r['stats']['t07_mean']}K | T07 máx: {r['stats']['t07_max']}K | Cand. fogo: {r['fire_pixels_count']}")
else:
    lines.append("- Nenhum dado GOES com cobertura do Ceará disponível neste ciclo.")
    lines.append("- GOES-16 (75.2°W) — satélite que cobre o Brasil — dados CMIPF não disponíveis via S3 público para 2026.")

lines.append("")

# Check if we processed new data vs previous report
prev_goes_ts = None
for line in prev.split('\n'):
    m = re.search(r'\*\*Timestamp:\*\* (.*? UTC)', line)
    if m: prev_goes_ts = m.group(1)
if best_goes:
    current_ts = best_goes[1]['timestamp']
    if prev_goes_ts and current_ts != prev_goes_ts:
        lines.append(f"> 📡 **Novo scan processado:** {prev_goes_ts} → {current_ts}")
    elif prev_goes_ts:
        lines.append(f"> 📡 **Mesmo scan do relatório anterior:** {current_ts}")

lines.append("")

# Sources note
lines.append("**Fontes:**")
lines.append("- INPE BDQueimadas — Programa Queimadas")
lines.append("- GOES-19 ABI L2 CMIPF — Bandas 07 (3.9µm) e 13 (10.4µm) via AWS Open Data")
lines.append("- Algoritmo: K-Means (k=4) + limiar termal (T07 ≥ 315K + BTD > 2K)")
lines.append("- **Próxima execução:** Cron job automático — verifica novos dados a cada ciclo")

report_content = "\n".join(lines)

# Save report
timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
report_path = os.path.join(OUTPUT_DIR, f"cron-{timestamp}.md")
with open(report_path, 'w') as f:
    f.write(report_content)

print(report_content)

# Save JSON
json_path = os.path.join(OUTPUT_DIR, "last_run.json")
try:
    with open(json_path, 'w') as f:
        json.dump({"timestamp": timestamp, "inpe_ce_anual": results['inpe']['ce_anual_2026']}, f)
except: pass

report(f"\nRelatório salvo: {report_path}")
report("="*60)
report("FIM")
report("="*60)
