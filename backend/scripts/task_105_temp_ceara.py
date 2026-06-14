#!/usr/bin/env python3
"""Analyze GOES-19 C07 temperatures over Ceará only for TASK-105."""
import numpy as np
import netCDF4 as nc
import os, json, math, re
from datetime import datetime, timezone
from pyproj import Proj

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
OUTPUT = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts/TASK-105-temperature-analysis.json"

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25
SAT_LON = -75.0
H, R_EQ, R_POL = 35786023.0, 6378137.0, 6356752.3142
GEOS_PROJ = Proj(proj="geos", lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)

def fixed_grid_to_latlon(x_rad, y_rad):
    x = np.asarray(x_rad, dtype=np.float64)
    y = np.asarray(y_rad, dtype=np.float64)
    return GEOS_PROJ(H * np.tan(x), H * np.tan(y) / np.cos(x), inverse=True)

files = sorted([f for f in os.listdir(DATA_DIR) if "M6C07_G19" in f and f.endswith(".nc")])
results = {}
for fname in files[-15:]:
    try:
        path = os.path.join(DATA_DIR, fname)
        ds = nc.Dataset(path)
        c07 = np.array(ds.variables["CMI"][:], dtype=np.float64)
        x_v = ds.variables["x"][:]
        y_v = ds.variables["y"][:]
        ds.close()
        
        # Mask invalid data
        mask = (c07 < 150) | (c07 > 500)
        c07_masked = np.ma.masked_where(mask, c07)
        
        xx, yy = np.meshgrid(x_v, y_v)
        lat_arr, lon_arr = fixed_grid_to_latlon(xx, yy)
        
        # Ceará bounding box
        idx = np.where(
            (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
            (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
        )
        
        if len(idx[0]) == 0:
            continue
        
        ce_pixels = c07_masked[idx]
        valid_pixels = ce_pixels[~ce_pixels.mask]
        
        key = os.path.basename(fname)
        results[key] = {
            "ce_pixels": len(idx[0]),
            "valid_pixels": len(valid_pixels),
            "min_k": float(np.min(valid_pixels)) if len(valid_pixels) > 0 else None,
            "max_k": float(np.max(valid_pixels)) if len(valid_pixels) > 0 else None,
            "mean_k": round(float(np.mean(valid_pixels)), 2) if len(valid_pixels) > 0 else None,
            "std_k": round(float(np.std(valid_pixels)), 2) if len(valid_pixels) > 0 else None,
            "over_300K": int(np.sum(valid_pixels > 300)) if len(valid_pixels) > 0 else 0,
            "over_310K": int(np.sum(valid_pixels > 310)) if len(valid_pixels) > 0 else 0,
            "over_315K": int(np.sum(valid_pixels > 315)) if len(valid_pixels) > 0 else 0,
        }
    except Exception as e:
        pass

with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)

print(f"Temperature analysis (Ceará only) saved: {len(results)} files")
for k, v in sorted(results.items()):
    tmax = v.get("max_k", "N/A")
    over310 = v.get("over_310K", 0)
    print(f"  {k[29:48]}: Tmax={tmax}K, >310K={over310} pixels CE")
