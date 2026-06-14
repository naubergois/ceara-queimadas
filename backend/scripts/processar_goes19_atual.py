#!/usr/bin/env python3
"""
Processa dados GOES-19 DOY 165 H00 (recém-baixados)
Gera relatório de status do pipeline.
"""
import os, sys, json, re
import numpy as np
import netCDF4 as nc
from sklearn.cluster import KMeans
from pyproj import Proj
from datetime import datetime, timedelta, timezone
import math

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
os.chdir(DATA_DIR)

SAT_LON = -75.0
H = 35786023.0
R_EQ = 6378137.0
R_POL = 6356752.3142
GEOS_PROJ = Proj(proj='geos', lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

def fixed_grid_to_latlon(x_rad, y_rad):
    x = np.asarray(x_rad, dtype=np.float64)
    y = np.asarray(y_rad, dtype=np.float64)
    X = H * np.tan(x)
    Y = H * np.tan(y) / np.cos(x)
    lon, lat = GEOS_PROJ(X, Y, inverse=True)
    return np.asarray(lat), np.asarray(lon)

def extract_timestamp(filepath):
    fname = os.path.basename(filepath)
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hr), minutes=int(mi), seconds=int(sc))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return 'unknown'

now = datetime.now(timezone.utc)
doy_now = now.timetuple().tm_yday
ts_now = now.strftime('%Y-%m-%d %H:%M:%S UTC')

print("=" * 65)
print(f"PIPELINE GOES-19 — Coleta de Dados")
print(f"Timestamp: {ts_now} (DOY {doy_now})")
print("=" * 65)

c07_path = 'GOES19_C07_165_00.nc'
c13_path = 'GOES19_C13_165_00.nc'
c14_path = 'GOES19_C14_165_00.nc'
fdcf_path = 'GOES19_FDCF_165_00.nc'

missing = [p for p in [c07_path, c13_path, c14_path, fdcf_path] if not os.path.exists(p)]
if missing:
    print(f"❌ Arquivos faltando: {missing}")
    print("Execute os downloads primeiro:")
    print("  aws s3 cp s3://noaa-goes19/ABI-L2-CMIPF/2026/165/00/ ... --no-sign-request --region us-east-1")
    sys.exit(1)

# Verify files
for p in [c07_path, c13_path, c14_path, fdcf_path]:
    sz = os.path.getsize(p) / 1e6
    ts = extract_timestamp(p)
    print(f"✅ {p} ({sz:.1f} MB) — {ts}")

# Open datasets
print("\n--- CMIPF Processing ---")
ds7 = nc.Dataset(c07_path)
ds13 = nc.Dataset(c13_path)
ds14 = nc.Dataset(c14_path)

c07 = np.array(ds7.variables['CMI'][:], dtype=np.float64)
c13 = np.array(ds13.variables['CMI'][:], dtype=np.float64)
c14 = np.array(ds14.variables['CMI'][:], dtype=np.float64)

x_v = ds7.variables['x'][:]
y_v = ds7.variables['y'][:]
xx, yy = np.meshgrid(x_v, y_v)
lat_arr, lon_arr = fixed_grid_to_latlon(xx, yy)
ts = extract_timestamp(c07_path)

# Ceará mask
idx = np.where(
    (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
    (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
)

print(f"Pixels no Ceará: {len(idx[0])} / {len(lat_arr.flatten())} total")

# Thermal analysis
ce_temps = []
ce_pixels = []
for i in range(len(idx[0])):
    yi, xi = idx[0][i], idx[1][i]
    t7 = float(c07[yi, xi])
    t13 = float(c13[yi, xi])
    t14 = float(c14[yi, xi])
    if not np.isnan(t7) and not np.isnan(t13):
        btd = t7 - t14
        ce_temps.append(t7)
        ce_pixels.append({
            'yi': yi, 'xi': xi,
            'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
            't07': t7, 't13': t13, 't14': t14, 'btd_7_14': btd,
        })

ce_arr = np.array(ce_temps)
stats = {
    'min_k': round(float(ce_arr.min()), 1),
    'max_k': round(float(ce_arr.max()), 1),
    'mean_k': round(float(ce_arr.mean()), 1),
    'pixels_above_310k': int(np.sum(ce_arr > 310)),
    'pixels_above_320k': int(np.sum(ce_arr > 320)),
    'pixels_above_330k': int(np.sum(ce_arr > 330)),
}

print(f"Temps Ceará (C07): min={stats['min_k']}K max={stats['max_k']}K mean={stats['mean_k']}K")
print(f"Pixels >310K: {stats['pixels_above_310k']} | >320K: {stats['pixels_above_320k']} | >330K: {stats['pixels_above_330k']}")

# Threshold fire detection
fire_threshold = []
for p in ce_pixels:
    if p['t07'] > 310 and p['btd_7_14'] > 2:
        fire_threshold.append({
            'lat': round(p['lat'], 4),
            'lon': round(p['lon'], 4),
            't07': round(p['t07'], 1),
            't13': round(p['t13'], 1),
            'btd': round(p['btd_7_14'], 1),
        })

print(f"\nFire detections (threshold 310K+BTD>2): {len(fire_threshold)}")
for fp in fire_threshold[:5]:
    print(f"  [{ts[:16]}] lat={fp['lat']} lon={fp['lon']} T07={fp['t07']}K BTD={fp['btd']}K")

# FDCF Processing
print("\n--- FDCF Processing ---")
fds = nc.Dataset(fdcf_path)
dqf = np.array(fds.variables['DQF'][:], dtype=np.int32)
temp = np.array(fds.variables['Temp'][:], dtype=np.float64)
power = np.array(fds.variables['Power'][:], dtype=np.float64)

fs_x = fds.variables['x'][:]
fs_y = fds.variables['y'][:]
fxx, fyy = np.meshgrid(fs_x, fs_y)
flat_f, flon_f = fixed_grid_to_latlon(fxx, fyy)

fire_mask = dqf == 0
ce_fire = np.where(fire_mask &
    (flat_f >= CEARA_LAT_MIN) & (flat_f <= CEARA_LAT_MAX) &
    (flon_f >= CEARA_LON_MIN) & (flon_f <= CEARA_LON_MAX))

fdcf_results = []
for i in range(len(ce_fire[0])):
    yi, xi = ce_fire[0][i], ce_fire[1][i]
    fdcf_results.append({
        'lat': round(float(flat_f[yi, xi]), 4),
        'lon': round(float(flon_f[yi, xi]), 4),
        'temp_k': round(float(temp[yi, xi]), 1),
        'frp_mw': round(float(power[yi, xi]), 1),
    })

print(f"FDCF fire pixels Ceará: {len(fdcf_results)}")
for fp in fdcf_results[:5]:
    print(f"  FDCF: lat={fp['lat']} lon={fp['lon']} T={fp['temp_k']}K FRP={fp['frp_mw']}MW")

ds7.close(); ds13.close(); ds14.close(); fds.close()

# Summary
total = len(fire_threshold) + len(fdcf_results)
result = {
    'timestamp': ts_now,
    'satellite': 'GOES-19 (75.2°W) via pyproj',
    'data_doy': 165,
    'data_hour': 0,
    'data_time': ts,
    'ceara_total_pixels': int(len(idx[0])),
    'thermal_stats': stats,
    'threshold_detections': len(fire_threshold),
    'fdcf_detections': len(fdcf_results),
    'total_detections': total,
    'winter_season': stats['max_k'] < 310,
}

out_path = os.path.join(DATA_DIR, 'goes19_detection_results.json')
with open(out_path, 'w') as f:
    json.dump(result, f, indent=2)

print(f"\n{'='*65}")
print(f"RESUMO: {total} detecções (threshold={len(fire_threshold)}, FDCF={len(fdcf_results)})")
print(f"Estação: {'🌧️ INVERNO CE (sem queimadas ativas)' if stats['max_k'] < 310 else '☀️ ESTAÇÃO SECA'}")
print(f"Resultados salvos em: {out_path}")
print(f"{'='*65}")
