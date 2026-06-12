#!/usr/bin/env python3
"""Debug: check actual temperature values in GOES C07/C13 for CE pixels."""
import os, sys, re, math
from datetime import datetime, timedelta, timezone
import numpy as np
import netCDF4 as nc
from pyproj import Proj

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
CE_LAT_MIN, CE_LAT_MAX = -7.85, -2.78
CE_LON_MIN, CE_LON_MAX = -41.42, -37.25
SAT_LON = -75.0
H, R_EQ, R_POL = 35786023.0, 6378137.0, 6356752.3142
GEOS_PROJ = Proj(proj='geos', lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)

def to_latlon(x_rad, y_rad):
    x = np.asarray(x_rad, dtype=np.float64)
    y = np.asarray(y_rad, dtype=np.float64)
    return GEOS_PROJ(H * np.tan(x), H * np.tan(y) / np.cos(x), inverse=True)

# Test DOY 158, 13z
c07_path = os.path.join(DATA_DIR, "OR_ABI-L2-CMIPF-M6C07_G19_s20261581350217_e20261581359537_c20261581359579.nc")
c13_path = os.path.join(DATA_DIR, "OR_ABI-L2-CMIPF-M6C13_G19_s20261581350217_e20261581359537_c20261581359579.nc")
c14_path = os.path.join(DATA_DIR, "GOES19_C14_155_15.nc")  # Older but available

for path, label in [(c07_path, "C07"), (c13_path, "C13")]:
    ds = nc.Dataset(path)
    var_name = 'CMI'
    print(f"\n{label} ({os.path.basename(path)}):")
    data = np.array(ds.variables[var_name][:], dtype=np.float64)
    print(f"  Shape: {data.shape}")
    print(f"  Dtype: {data.dtype}")
    print(f"  Min: {np.nanmin(data):.2f} K")
    print(f"  Max: {np.nanmax(data):.2f} K")
    print(f"  Mean: {np.nanmean(data):.2f} K")
    print(f"  NaN count: {np.isnan(data).sum()}")
    
    # Check valid_range
    v = ds.variables[var_name]
    if hasattr(v, 'valid_range'):
        print(f"  valid_range: {v.valid_range}")
    if hasattr(v, 'scale_factor'):
        print(f"  scale_factor: {v.scale_factor}, add_offset: {v.add_offset}")
    
    # Check Ceará values
    x_v = ds.variables['x'][:]
    y_v = ds.variables['y'][:]
    xx, yy = np.meshgrid(x_v, y_v)
    lat_arr, lon_arr = to_latlon(xx, yy)
    idx = np.where((lat_arr >= CE_LAT_MIN) & (lat_arr <= CE_LAT_MAX) &
                   (lon_arr >= CE_LON_MIN) & (lon_arr <= CE_LON_MAX))
    ce_data = data[idx]
    print(f"  CE pixels: {len(ce_data)}")
    print(f"  CE Min: {np.nanmin(ce_data):.2f} K")
    print(f"  CE Max: {np.nanmax(ce_data):.2f} K")
    print(f"  CE Mean: {np.nanmean(ce_data):.2f} K")
    print(f"  CE > 310K: {(ce_data > 310).sum()}")
    print(f"  CE > 320K: {(ce_data > 320).sum()}")
    print(f"  CE > 330K: {(ce_data > 330).sum()}")
    
    # Show top 10 hottest
    sorted_idx = np.argsort(ce_data.flatten())[-10:][::-1]
    print(f"  Top 10 hottest CE pixels (K): {[f'{ce_data.flatten()[i]:.1f}' for i in sorted_idx]}")
    ds.close()

# Also test with old GOES19_C14 file
print(f"\nC14 (GOES19_C14_155_15.nc):")
ds = nc.Dataset(c14_path)
try:
    data = np.array(ds.variables['CMI'][:], dtype=np.float64)
    print(f"  Shape: {data.shape}")
    print(f"  Min: {np.nanmin(data):.2f} K")
    print(f"  Max: {np.nanmax(data):.2f} K")
    print(f"  Mean: {np.nanmean(data):.2f} K")
except Exception as e:
    print(f"  Error: {e}")
    # Try variable auto-detect
    for v in ds.variables:
        if v not in ['x','y','t','goes_imager_projection','spatial_ref']:
            try:
                data = np.array(ds.variables[v][:], dtype=np.float64)
                print(f"  Var '{v}': shape={data.shape}, min={np.nanmin(data):.2f}, max={np.nanmax(data):.2f}")
            except: pass
ds.close()
