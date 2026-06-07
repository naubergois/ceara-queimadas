#!/usr/bin/env python3
"""Quick check legacy FDCF fire counts per file."""
import os, numpy as np, netCDF4 as nc

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

def goes_latlon(x, y, sat_lon):
    import math
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
    if not (fname.startswith("GOES19_FDCF_") and fname.endswith(".nc")):
        continue
    fpath = os.path.join(BASE, fname)
    ds = nc.Dataset(fpath)
    sat_lon = float(ds['nominal_satellite_subpoint_lon'][:])
    total = int(ds['total_number_of_pixels_with_fires_detected'][:])
    mask = np.array(ds['Mask'][:], dtype=int)
    if hasattr(mask, 'data'):
        mask = mask.data
    fire = (mask == 200) | (mask == 201) | (mask == 215) | (mask == 220)
    n_fire = int(np.sum(fire))
    x_arr = ds['x'][:].astype(float)
    y_arr = ds['y'][:].astype(float)
    fi = np.where(fire)
    ce = 0
    for i in range(min(n_fire, 100000)):
        yi, xi = fi[0][i], fi[1][i]
        lv, lv2 = goes_latlon(x_arr[xi], y_arr[yi], sat_lon)
        if CEARA_LAT_MIN <= lv <= CEARA_LAT_MAX and CEARA_LON_MIN <= lv2 <= CEARA_LON_MAX:
            ce += 1
    print(f"{fname}: total_detected={total}, fire_px={n_fire}, ce_fires={ce}")
    ds.close()
