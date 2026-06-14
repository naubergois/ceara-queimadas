#!/usr/bin/env python3
"""Analyze GOES-19 C07 temperatures for TASK-105 seasonal analysis."""
import numpy as np
import netCDF4 as nc
import os, json

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
OUTPUT = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts/TASK-105-temperature-analysis.json"

files = sorted([f for f in os.listdir(DATA_DIR) if "M6C07_G19" in f and f.endswith(".nc")])
results = {}
for fname in files[-15:]:
    try:
        path = os.path.join(DATA_DIR, fname)
        ds = nc.Dataset(path)
        c07 = np.array(ds.variables["CMI"][:], dtype=np.float64)
        ds.close()
        key = fname[29:43]
        results[key] = {
            "min": round(float(np.nanmin(c07)), 2),
            "max": round(float(np.nanmax(c07)), 2),
            "mean": round(float(np.nanmean(c07)), 2),
            "pixels_over_300K": int(np.sum(c07 > 300)),
            "pixels_over_310K": int(np.sum(c07 > 310)),
            "pixels_over_315K": int(np.sum(c07 > 315)),
        }
    except Exception as e:
        pass

with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"Temperature analysis saved to {OUTPUT}")
print(f"Files analyzed: {len(results)}")
for k, v in sorted(results.items()):
    print(f"  {k}: max={v['max']}K, >310K={v['pixels_over_310K']} pixels")
