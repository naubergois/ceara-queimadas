#!/usr/bin/env python3
"""Check legacy GOES-19 FDCF for fires over Ceará."""
import os, json, math, re
from datetime import datetime, timedelta, timezone
import netCDF4 as nc
import numpy as np

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
CE_MUN_FIRES = [
    # Known INPE fires reference from previous runs
    {"lat": -4.36, "lon": -37.90, "name": "Beberibe"},
    {"lat": -6.63, "lon": -38.73, "name": "Cajazeiras/PB border"},
    {"lat": -6.59, "lon": -39.64, "name": "Jaguaribe"},
    {"lat": -6.61, "lon": -39.07, "name": "Ipaumirim"},
    {"lat": -5.06, "lon": -39.94, "name": "Canindé"},
]

def goes_latlon(x, y, sat_lon):
    a, b, h_val = 6378137.0, 6356752.31414, 35786023.0
    l0 = math.radians(sat_lon)
    xr = x/h_val; yr = y/h_val
    cx = math.cos(xr); sx = math.sin(xr)
    cy = math.cos(yr); sy = math.sin(yr)
    a2, b2, h2 = a*a, b*b, h_val*h_val
    at = sx*sx + cx*cx*(cy*cy + (a2/b2)*sy*sy)
    B = -2*h_val*cx*cy
    ct = h2 - a2
    sd = (-B - math.sqrt(max(B*B - 4*at*ct, 0)))/(2*at)
    lat = math.degrees(math.atan2(-cx*sy, math.sqrt(max(cy*cy + (a2/b2)*sx*sx*sy*sy, 0))))
    lon = math.degrees(l0 + math.atan2(sd*sx*cy, h_val - sd*cx*cy))
    return lat, lon

for fname in sorted(os.listdir(BASE)):
    # Check legacy naming
    m = re.search(r'GOES19_FDCF_(\d{3})_(\d{2})\.nc', fname)
    if not m:
        continue
    doy, hour = int(m.group(1)), int(m.group(2))
    fpath = os.path.join(BASE, fname)
    try:
        ds = nc.Dataset(fpath)
    except:
        continue
    
    sat_lon = float(ds.variables['nominal_satellite_subpoint_lon'][:])
    
    # Legacy FDCF structure
    print(f"\n{'='*60}")
    print(f"File: {fname} (DOY{doy} H{hour:02d}Z)")
    print(f"Variables: {list(ds.variables.keys())}")
    
    if 'FDCF' in ds.variables:
        data = np.array(ds['FDCF'][:])
        if hasattr(data, 'mask') and np.ma.is_masked(data):
            data = data.data
        vals, counts = np.unique(data, return_counts=True)
        fire_vals = [v for v in vals if v > 0]
        print(f"FDCF non-zero values: {[(int(v), int(c)) for v, c in zip(vals, counts) if v > 0][:20]}")
        
        # Get x,y
        if 'x' in ds.variables:
            x_arr = ds['x'][:].astype(float)
            y_arr = ds['y'][:].astype(float)
            
            # For each fire pixel, compute lat/lon
            fire_mask = data > 0
            fire_idx = np.where(fire_mask)
            
            total_fire = len(fire_idx[0])
            ce_fires = 0
            for i in range(total_fire):
                yi, xi = fire_idx[0][i], fire_idx[1][i]
                lat_v, lon_v = goes_latlon(x_arr[xi], y_arr[yi], sat_lon)
                if CEARA_LAT_MIN <= lat_v <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon_v <= CEARA_LON_MAX:
                    ce_fires += 1
            
            print(f"Total fire pixels: {total_fire}, Ceará: {ce_fires}")
        else:
            print(f"FDCF shape: {data.shape}")
    elif 'Mask' in ds.variables:
        mask = np.array(ds['Mask'][:], dtype=int)
        if hasattr(mask, 'data'):
            mask = mask.data
        fire_mask = (mask == 200) | (mask == 201) | (mask == 215) | (mask == 220)
        total = np.sum(fire_mask)
        
        x_arr = ds['x'][:].astype(float)
        y_arr = ds['y'][:].astype(float)
        fire_idx = np.where(fire_mask)
        ce_fires = 0
        for i in range(min(total, 50000)):
            yi, xi = fire_idx[0][i], fire_idx[1][i]
            lat_v, lon_v = goes_latlon(x_arr[xi], y_arr[yi], sat_lon)
            if CEARA_LAT_MIN <= lat_v <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon_v <= CEARA_LON_MAX:
                ce_fires += 1
        print(f"Total fire pixels(mask=200+): {total}, Ceará: {ce_fires}")
    else:
        print("No FDCF or Mask variable found")
    
    ds.close()

print("\n\n=== SUMMARY ===")
print("Total GOES-19 FDCF files with fires in Ceará: (checked above)")
