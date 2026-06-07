#!/usr/bin/env python3
"""Inspect FDCF file variables."""
import netCDF4 as nc
import sys

fpath = sys.argv[1]
ds = nc.Dataset(fpath)
print("Variables:", list(ds.variables.keys()))
print("Dimensions:", {k: len(v) for k, v in ds.dimensions.items()})
print("Groups:", list(ds.groups.keys()) if hasattr(ds, 'groups') else "none")
for vname in sorted(ds.variables.keys()):
    v = ds.variables[vname]
    print(f"  {vname}: shape={v.shape}, dtype={v.dtype}, dims={v.dimensions}")
ds.close()
