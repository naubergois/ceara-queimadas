#!/usr/bin/env python3
"""Process GOES-19 today (DOY157) — latest daytime scan for fire detection."""
import sys, json, os
from datetime import datetime, timezone

# Patch: update cron_analysis paths and sat_lon for GOES-19 (75.2W)
sys.path.insert(0, '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/scripts')
from cron_analysis import report, CEARA_LAT_MIN, CEARA_LAT_MAX, CEARA_LON_MIN, CEARA_LON_MAX

import netCDF4 as nc
import numpy as np
from sklearn.cluster import KMeans
import math, re

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
OUTPUT_DIR = "/Users/naubergois/.hermes/profiles/analista-queimadas/cron/output"

GOES19_LON = -75.0

def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a = 6378137.0
    b = 6356752.31414
    h = 35786023.0
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
    lat = np.degrees(np.arctan2(-cos_x * sin_y, np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq) * sin_x**2 * sin_y**2, 0))))
    lon = np.degrees(lambda_0 + np.arctan2(s_d * sin_x * cos_y, h - s_d * cos_x * cos_y))
    return lat, lon

def extract_timestamp_individual(fname):
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', fname)
    if m:
        year, doy, hour, minute, second = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hour), minutes=int(minute), seconds=int(second))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

from datetime import timedelta

# Find latest daytime scan (hour 08-12 UTC)
c07_files = sorted([f for f in os.listdir(BASE) if f.startswith('OR_ABI-L2-CMIPF-M6C07') and '2026157' in f and f.endswith('.nc')])
c13_files = sorted([f for f in os.listdir(BASE) if f.startswith('OR_ABI-L2-CMIPF-M6C13') and '2026157' in f and f.endswith('.nc')])

print(f"C07 files: {len(c07_files)}")
print(f"C13 files: {len(c13_files)}")

# Match pairs by timestamp (sYYYYDDDHHMMSS pattern)
c07_timestamps = {}
for f in c07_files:
    m = re.search(r'_s(\d{14})', f)
    if m: c07_timestamps[m.group(1)] = f

c13_timestamps = {}
for f in c13_files:
    m = re.search(r'_s(\d{14})', f)
    if m: c13_timestamps[m.group(1)] = f

# Find matching timestamps
common_ts = sorted(set(c07_timestamps.keys()) & set(c13_timestamps.keys()))
print(f"Common scan timestamps: {len(common_ts)}")
for ts in common_ts:
    # Extract HHMM from timestamp
    hh = ts[8:10]
    mm = ts[10:12]
    print(f"  ts={ts}: {hh}:{mm}Z -> C07={c07_timestamps[ts]}, C13={c13_timestamps[ts]}")

# Process the latest scan
if common_ts:
    latest_ts = common_ts[-1]
    c07_file = os.path.join(BASE, c07_timestamps[latest_ts])
    c13_file = os.path.join(BASE, c13_timestamps[latest_ts])
    
    print(f"\n{'='*60}")
    print(f"Processing latest scan: {latest_ts}")
    print(f"C07: {c07_timestamps[latest_ts]}")
    print(f"C13: {c13_timestamps[latest_ts]}")
    print(f"{'='*60}")
    
    ds7 = nc.Dataset(c07_file)
    ds13 = nc.Dataset(c13_file)
    
    x_var = ds7.variables['x']
    y_var = ds7.variables['y']
    
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(
        np.meshgrid(x_var[:], y_var[:])[0],
        np.meshgrid(x_var[:], y_var[:])[1],
        GOES19_LON
    )
    
    c07 = ds7.variables['CMI'][:] * ds7.variables['CMI'].scale_factor + ds7.variables['CMI'].add_offset
    c13 = ds13.variables['CMI'][:] * ds13.variables['CMI'].scale_factor + ds13.variables['CMI'].add_offset
    
    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )
    
    pixels_ceara = len(idx[0])
    print(f"Pixels in Ceará: {pixels_ceara}")
    
    # Extract pixel data
    pixel_list = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t07_v = c07[yi, xi] if c07.ndim == 2 else c07[0, yi, xi]
        t13_v = c13[yi, xi] if c13.ndim == 2 else c13[0, yi, xi]
        if np.ma.is_masked(t07_v) or np.ma.is_masked(t13_v):
            continue
        t07 = float(t07_v)
        t13 = float(t13_v)
        if math.isnan(t07) or math.isnan(t13):
            continue
        pixel_list.append({
            'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
            't07': t07, 't13': t13, 'btd': t07 - t13,
        })
    
    valid = len(pixel_list)
    print(f"Valid pixels: {valid}")
    
    if valid > 0:
        temps_t07 = [p['t07'] for p in pixel_list]
        btds = [p['btd'] for p in pixel_list]
        print(f"T07: {min(temps_t07):.1f}K - {max(temps_t07):.1f}K (mean={np.mean(temps_t07):.1f}K)")
        print(f"BTD: {min(btds):.1f}K - {max(btds):.1f}K (mean={np.mean(btds):.1f}K)")
        
        # Fire detection
        fire_315 = [p for p in pixel_list if p['t07'] >= 315 and p['btd'] > 2]
        fire_320 = [p for p in pixel_list if p['t07'] >= 320 and p['btd'] > 3]
        fire_330 = [p for p in pixel_list if p['t07'] >= 330 and p['btd'] > 5]
        
        print(f"\nFire candidates:")
        print(f"  ≥315K+B2K: {len(fire_315)}")
        print(f"  ≥320K+B3K: {len(fire_320)}")
        print(f"  ≥330K+B5K: {len(fire_330)}")
        
        if fire_315:
            print(f"\nTop 10 hotspots by T07:")
            for h in sorted(fire_315, key=lambda x: x['t07'], reverse=True)[:10]:
                print(f"  ({h['lat']:.4f}, {h['lon']:.4f}) T07={h['t07']:.1f}K BTD={h['btd']:.1f}K")
        
        # K-Means clustering
        if valid >= 10:
            indices = np.linspace(0, valid-1, min(3000, valid), dtype=int)
            sampled = [pixel_list[i] for i in indices]
            features = np.array([[p['t07'], p['t13'], p['btd']] for p in sampled])
            valid_idx = ~np.any(np.isnan(features), axis=1)
            features = features[valid_idx]
            
            if len(features) >= 10:
                f_mean = features.mean(axis=0)
                f_std = features.std(axis=0) + 1e-10
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
                
                print(f"\nK-Means Clusters:")
                for label, data in sorted(cluster_profiles.items(), key=lambda x: np.mean(x[1]['t07']), reverse=True):
                    mean_t07 = np.mean(data['t07'])
                    mean_btd = np.mean(data['btd'])
                    is_fire = mean_t07 > 315 and mean_btd > 2
                    mark = "🔥" if is_fire else "🌲" if mean_t07 < 300 else "⛅"
                    pct = data['count']/len(labels)*100
                    print(f"  {mark} Cluster {label}: {pct:.1f}% | T07={mean_t07:.1f}K | BTD={mean_btd:.1f}K")
    
    ds7.close()
    ds13.close()
    
    # Save results
    result = {
        "timestamp": extract_timestamp_individual(c07_timestamps[latest_ts]),
        "satellite": "GOES-19",
        "scan": f"DOY157_{latest_ts[8:10]}Z",
        "pixels_ceara": pixels_ceara,
        "valid_pixels": valid,
        "fire_315k": len(fire_315),
        "fire_320k": len(fire_320),
        "fire_330k": len(fire_330),
        "t07_range": {"min": round(min(temps_t07),1), "max": round(max(temps_t07),1), "mean": round(np.mean(temps_t07),1)} if temps_t07 else None,
        "btd_range": {"min": round(min(btds),1), "max": round(max(btds),1), "mean": round(np.mean(btds),1)} if btds else None,
    }
    
    json_path = os.path.join(BASE, f"goes19_doy157_analysis.json")
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {json_path}")

print(f"\nDone at {datetime.now().strftime('%H:%M:%S')}")
