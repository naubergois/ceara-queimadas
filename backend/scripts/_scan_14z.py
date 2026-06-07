#!/usr/bin/env python3
"""Analyze GOES-19 14:40Z scan for fire detection in Ceará."""
import sys, os, json, math, re
from datetime import datetime, timezone, timedelta
import netCDF4 as nc
import numpy as np

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25


def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a, b, h = 6378137.0, 6356752.31414, 35786023.0
    lambda_0 = math.radians(sat_lon_deg)
    x = np.array(x_arr, dtype=np.float64)
    y = np.array(y_arr, dtype=np.float64)
    cos_x, sin_x = np.cos(x), np.sin(x)
    cos_y, sin_y = np.cos(y), np.sin(y)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    B = -2.0*h*cos_x*cos_y
    c_term = h_sq - a_sq
    sd = np.sqrt(np.maximum(B*B - 4*a_term*c_term, 0))
    s_d = (-B - sd)/(2*a_term)
    lat = np.degrees(np.arctan2(-cos_x*sin_y, np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq)*sin_x**2*sin_y**2, 0))))
    lon = np.degrees(lambda_0 + np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y))
    return lat, lon


def extract_ts(fpath):
    fname = os.path.basename(fpath)
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', fname)
    if m:
        y, d, h, mi, s = m.groups()
        dt = datetime(int(y), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(d)-1, hours=int(h), minutes=int(mi), seconds=int(s))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return 'unknown'


c07_path = os.path.join(BASE, 'OR_ABI-L2-CMIPF-M6C07_G19_s20261571440216_e20261571449536_c20261571449590.nc')
c13_path = os.path.join(BASE, 'OR_ABI-L2-CMIPF-M6C13_G19_s20261571440216_e20261571449536_c20261571449580.nc')

if not os.path.exists(c07_path) or not os.path.exists(c13_path):
    print("ERROR: Data files not found")
    sys.exit(1)

print(f'C07: {os.path.getsize(c07_path)/1e6:.1f} MB')
print(f'C13: {os.path.getsize(c13_path)/1e6:.1f} MB')

ds7 = nc.Dataset(c07_path)
ds13 = nc.Dataset(c13_path)

proj = None
if 'goes_imager_projection' in ds7.variables:
    proj = ds7.variables['goes_imager_projection']
if proj is not None:
    try:
        sat_lon = float(getattr(proj, 'longitude_of_projection_origin', -75.0))
        if sat_lon == 0.0: sat_lon = -75.0
        print(f'Satellite longitude from file: {sat_lon:.1f}°')
    except:
        sat_lon = -75.0
else:
    sat_lon = -75.0

x = ds7.variables['x'][:]
y = ds7.variables['y'][:]
lat_arr, lon_arr = goes_fixed_grid_to_latlon(np.meshgrid(x, y)[0], np.meshgrid(x, y)[1], sat_lon)

sf7, of7 = ds7.variables['CMI'].scale_factor, ds7.variables['CMI'].add_offset
sf13, of13 = ds13.variables['CMI'].scale_factor, ds13.variables['CMI'].add_offset
c07 = ds7.variables['CMI'][:].astype(np.float64) * sf7 + of7
c13 = ds13.variables['CMI'][:].astype(np.float64) * sf13 + of13

idx = np.where(
    (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
    (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
)
pixels_ceara = len(idx[0])
print(f'Pixels in Ceara: {pixels_ceara}')

pixel_list = []
for i in range(len(idx[0])):
    yi, xi = idx[0][i], idx[1][i]
    t07_v = c07[yi, xi]
    t13_v = c13[yi, xi]
    if np.ma.is_masked(t07_v) or np.ma.is_masked(t13_v):
        continue
    t07 = float(t07_v)
    t13 = float(t13_v)
    if math.isnan(t07) or math.isnan(t13):
        continue
    pixel_list.append({'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]), 't07': t07, 't13': t13, 'btd': t07 - t13})

valid = len(pixel_list)
print(f'Valid pixels: {valid}')

results = {'satellite': 'GOES-19', 'timestamp': extract_ts(c07_path), 'pixels_ceara': pixels_ceara, 'valid_pixels': valid, 'scan_label': '14:40Z'}

if valid > 0:
    temps = [p['t07'] for p in pixel_list]
    btds = [p['btd'] for p in pixel_list]
    t07_min, t07_max, t07_mean = round(min(temps), 1), round(max(temps), 1), round(float(np.mean(temps)), 1)
    btd_min, btd_max, btd_mean = round(min(btds), 1), round(max(btds), 1), round(float(np.mean(btds)), 1)
    
    print(f'T07: {t07_min}K - {t07_max}K (mean={t07_mean}K)')
    print(f'BTD: {btd_min}K - {btd_max}K (mean={btd_mean}K)')
    
    fire_315 = [p for p in pixel_list if p['t07'] >= 315 and p['btd'] > 2]
    fire_320 = [p for p in pixel_list if p['t07'] >= 320 and p['btd'] > 3]
    fire_330 = [p for p in pixel_list if p['t07'] >= 330 and p['btd'] > 5]
    
    cloud_pixels = len([p for p in pixel_list if p['t07'] < 300])
    clear_pixels = len([p for p in pixel_list if p['t07'] >= 300])
    
    results['t07_range'] = {'min': t07_min, 'max': t07_max, 'mean': t07_mean}
    results['btd_range'] = {'min': btd_min, 'max': btd_max, 'mean': btd_mean}
    results['fire_315k'] = len(fire_315)
    results['fire_320k'] = len(fire_320)
    results['fire_330k'] = len(fire_330)
    results['cloud_pixels'] = cloud_pixels
    results['clear_pixels'] = clear_pixels
    
    print(f'\nFire candidates: >=315K+B2K: {len(fire_315)} | >=320K+B3K: {len(fire_320)} | >=330K+B5K: {len(fire_330)}')
    print(f'Cloud pixels (T07<300K): {cloud_pixels} ({cloud_pixels/valid*100:.1f}%)')
    print(f'Clear pixels (T07>=300K): {clear_pixels} ({clear_pixels/valid*100:.1f}%)')
    
    # K-Means
    from sklearn.cluster import KMeans
    kmeans_features = np.array([[p['t07'], p['t13'], p['btd']] for p in pixel_list])
    n_k = min(len(kmeans_features), 2000)
    indices = np.linspace(0, len(kmeans_features)-1, n_k, dtype=int)
    f = kmeans_features[indices]
    f_mean = f.mean(axis=0)
    f_std = f.std(axis=0) + 1e-10
    f_norm = (f - f_mean) / f_std
    kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(f_norm)
    cluster_data = {}
    for i, label in enumerate(labels):
        if label not in cluster_data:
            cluster_data[label] = {'t07': [], 'btd': [], 'count': 0}
        cluster_data[label]['t07'].append(f[i, 0])
        cluster_data[label]['btd'].append(f[i, 2])
        cluster_data[label]['count'] += 1
    
    kmeans_clusters = []
    for cl, data in sorted(cluster_data.items(), key=lambda x: np.mean(x[1]['t07']), reverse=True):
        mt = round(float(np.mean(data['t07'])), 1)
        mb = round(float(np.mean(data['btd'])), 1)
        pct = round(data['count']/len(labels)*100, 1)
        is_fire = mt > 315 and mb > 2
        fire_mark = 'FIRE' if is_fire else ('CLOUD' if mt < 300 else 'MIXED')
        print(f'  {fire_mark} Cluster {cl}: {pct}% | T07={mt}K | BTD={mb}K')
        kmeans_clusters.append({'cluster': int(cl), 'pct': pct, 'mean_t07': mt, 'mean_btd': mb, 'is_fire': is_fire})
    
    results['kmeans_clusters'] = kmeans_clusters
    
    if fire_315:
        hotspots = sorted(fire_315, key=lambda x: x['t07'], reverse=True)[:20]
        results['hotspots'] = [{'lat': round(h['lat'], 4), 'lon': round(h['lon'], 4), 't07': round(h['t07'], 1), 'btd': round(h['btd'], 1)} for h in hotspots]
        print(f'\n=== HOTSPOTS ({len(fire_315)}) ===')
        for h in hotspots[:10]:
            print(f'  ({h["lat"]:.4f}, {h["lon"]:.4f}) T07={h["t07"]:.1f}K BTD={h["btd"]:.1f}K')
    else:
        results['hotspots'] = []
    
    # Compare with previous scan
    for label, path in [('12:30Z', 'goes19_doy157_analysis.json'), ('13:50Z', 'goes19_doy157_13z_analysis.json')]:
        prev_path = os.path.join(BASE, path)
        if os.path.exists(prev_path):
            with open(prev_path) as f:
                prev = json.load(f)
            print(f'\n--- Comparison: {label} vs 14:40Z ---')
            prev_mean = prev.get('t07_range', {}).get('mean', 0)
            print(f'{label}: T07={prev_mean}K | fires={prev.get("fire_315k", 0)}')
            print(f'14:40Z: T07={t07_mean}K | fires={len(fire_315)}')

ds7.close()
ds13.close()

out_path = os.path.join(BASE, 'goes19_doy157_14z_analysis.json')
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved: {out_path}')
print('DONE')
