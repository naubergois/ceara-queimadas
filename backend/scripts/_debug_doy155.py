#!/usr/bin/env python3
"""Debug: check GOES19 Doy155 temps in CE."""
import os, numpy as np, netCDF4 as nc
from pyproj import Proj

D = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
SAT_LON, H, R_EQ, R_POL = -75.0, 35786023.0, 6378137.0, 6356752.3142
P = Proj(proj='geos', lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)
CE_LAT_MIN, CE_LAT_MAX = -7.85, -2.78
CE_LON_MIN, CE_LON_MAX = -41.42, -37.25

def to_latlon(x_rad, y_rad):
    x = np.asarray(x_rad, dtype=np.float64)
    y = np.asarray(y_rad, dtype=np.float64)
    return P(H * np.tan(x), H * np.tan(y) / np.cos(x), inverse=True)

def check(path, label):
    if not os.path.exists(path):
        print(f"{label}: FILE NOT FOUND")
        return
    ds = nc.Dataset(path)
    d = np.array(ds.variables['CMI'][:], dtype=np.float64)
    xv = ds.variables['x'][:]; yv = ds.variables['y'][:]
    xx, yy = np.meshgrid(xv, yv)
    la, lo = to_latlon(xx, yy)
    idx = np.where((la >= CE_LAT_MIN) & (la <= CE_LAT_MAX) & (lo >= CE_LON_MIN) & (lo <= CE_LON_MAX))
    cd = d[idx]
    print(f"{label}: max={np.nanmax(cd):.1f}K >310={int((cd > 310).sum())} >320={int((cd > 320).sum())} N={len(cd)}")
    # Show top 5
    for i, val in enumerate(np.sort(cd.flatten())[-5:][::-1]):
        print(f"   #{i+1}: {val:.1f}K")
    ds.close()

for h in [15, 16, 17, 18]:
    print(f"\nHour {h:02d}:")
    for b in ["C07","C13","C14"]:
        check(f"{D}/GOES19_{b}_155_{h:02d}.nc", f"  {b}")
