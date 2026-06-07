#!/usr/bin/env python3
"""Process one scan from today to debug the variable issue."""
import sys, json, os, math, re, numpy as np
import netCDF4 as nc

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

# Take the first C07 file
c07_files = sorted([f for f in os.listdir(BASE) if f.startswith('OR_ABI-L2-CMIPF-M6C07') and '2026157' in f and f.endswith('.nc')])
fname = c07_files[0]
print(f"File: {fname}")

ds = nc.Dataset(os.path.join(BASE, fname))
print(f"Variables: {list(ds.variables.keys())}")

cmi = ds.variables['CMI']
print(f"CMI shape: {cmi.shape}, ndim: {cmi.ndim}")
print(f"CMI scale_factor: {cmi.scale_factor}, add_offset: {cmi.add_offset}")

# Check x,y
x = ds.variables['x'][:]
y = ds.variables['y'][:]
print(f"x: min={x[0]}, max={x[-1]}, len={len(x)}")
print(f"y: min={y[0]}, max={y[-1]}, len={len(y)}")

ds.close()
