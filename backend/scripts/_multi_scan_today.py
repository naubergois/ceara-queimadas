#!/usr/bin/env python3
"""Process one scan per hour from today to check for fire."""
import sys, os, math, re, numpy as np
import netCDF4 as nc

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
GOES19_LON = -75.0
CEARA_LAT_MIN, CEARA_LAT_MAX, CEARA_LON_MIN, CEARA_LON_MAX = -7.85, -2.78, -41.42, -37.25

def goes_fixed_grid(lat, lon, sat_lon_deg):
    a, b, h = 6378137.0, 6356752.31414, 35786023.0
    lambda_0 = math.radians(sat_lon_deg)
    x = np.array(lon, dtype=np.float64)
    y = np.array(lat, dtype=np.float64)
    cos_x = np.cos(x); sin_x = np.sin(x)
    cos_y = np.cos(y); sin_y = np.sin(y)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    B = -2.0*h*cos_x*cos_y
    disc = np.sqrt(np.maximum(B*B - 4*a_term*(h_sq - a_sq), 0))
    s_d = (-B - disc)/(2*a_term)
    lat_geo = np.degrees(np.arctan2(-cos_x*sin_y, np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq)*sin_x**2*sin_y**2, 0))))
    lon_geo = np.degrees(lambda_0 + np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y))
    return lat_geo, lon_geo

# Build lookup: first scan per hour
c07_by_ts = {}
c13_by_ts = {}
for f in os.listdir(BASE):
    m = re.search(r'_s(\d{14})', f)
    if not m: continue
    ts = m.group(1)
    if f.startswith('OR_ABI-L2-CMIPF-M6C07') and '2026157' in f:
        if ts[:10] not in c07_by_ts:  # first per minute
            c07_by_ts[ts[:10]] = (ts, f)
    elif f.startswith('OR_ABI-L2-CMIPF-M6C13') and '2026157' in f:
        if ts[:10] not in c13_by_ts:
            c13_by_ts[ts[:10]] = (ts, f)

hourly_ts = sorted(set(c07_by_ts.keys()) & set(c13_by_ts.keys()))
print(f"GOES-19 DOY157 (June 6) hourly scans: {len(hourly_ts)}\n")

for hour_key in hourly_ts:
    ts, c07_name = c07_by_ts[hour_key]
    _, c13_name = c13_by_ts[hour_key]
    
    hh = ts[8:10]
    mm = ts[10:12]
    
    ds7 = nc.Dataset(os.path.join(BASE, c07_name))
    ds13 = nc.Dataset(os.path.join(BASE, c13_name))
    
    x_arr, y_arr = ds7.variables['x'][:], ds7.variables['y'][:]
    lat_grid, lon_grid = goes_fixed_grid(np.meshgrid(x_arr, y_arr)[0], np.meshgrid(x_arr, y_arr)[1], GOES19_LON)
    
    c07 = ds7.variables['CMI'][:] * ds7.variables['CMI'].scale_factor + ds7.variables['CMI'].add_offset
    c13 = ds13.variables['CMI'][:] * ds13.variables['CMI'].scale_factor + ds13.variables['CMI'].add_offset
    
    if c07.ndim > 2: c07 = c07[0]
    if c13.ndim > 2: c13 = c13[0]
    
    mask = (lat_grid >= CEARA_LAT_MIN) & (lat_grid <= CEARA_LAT_MAX) & (lon_grid >= CEARA_LON_MIN) & (lon_grid <= CEARA_LON_MAX)
    idx = np.where(mask)
    
    ce_t07 = c07[idx]
    ce_c13 = c13[idx]
    valid = ~np.ma.getmaskarray(ce_t07) & ~np.ma.getmaskarray(ce_c13) & ~np.isnan(ce_t07) & ~np.isnan(ce_c13)
    
    if np.sum(valid) > 0:
        t07 = ce_t07[valid]
        t13 = ce_c13[valid]
        btd = t07 - t13
        
        fire_315 = int(np.sum(t07 >= 315))
        fire_320 = int(np.sum((t07 >= 320) & (btd > 3)))
        fire_max = round(float(np.max(t07)), 1)
        t_mean = round(float(np.mean(t07)), 1)
        t_min = round(float(np.min(t07)), 1)
        
        # Weather classification
        if fire_315 > 0:
            weather = "🔥 FIRE DETECTED"
        elif t_mean > 300:
            weather = "☀️ Clear / warm surface"
        elif t_mean > 290:
            weather = "⛅ Partly cloudy"
        elif t_mean > 280:
            weather = "☁️ Cloudy"
        else:
            weather = "🌙 Night / heavy cloud"
        
        local_h = int(hh) - 3
        print(f"  {hh}:{mm}Z ({local_h:02d}:{mm} local) → "
              f"{np.sum(valid):>6,} px | T07: {t_min}-{fire_max}K μ={t_mean}K | "
              f"≥315K: {fire_315} | {weather}")
    else:
        print(f"  {hh}:{mm}Z → No valid pixels (all masked)")
    
    ds7.close()
    ds13.close()
