#!/usr/bin/env python3
import netCDF4 as nc, os

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
fname = "GOES19_C07_156_22.nc"
fpath = os.path.join(BASE, fname)
ds = nc.Dataset(fpath)
print("Variables:", list(ds.variables.keys())[:20])
print("---")

# Check x and y
if 'x' in ds.variables:
    x = ds.variables['x']
    print(f"x type: {type(x)}, shape: {x.shape}, len: {len(x)}")
if 'y' in ds.variables:
    y = ds.variables['y']
    print(f"y type: {type(y)}, shape: {y.shape}, len: {len(y)}")

# Check proj
if 'goes_imager_projection' in ds.variables:
    gip = ds.variables['goes_imager_projection']
    print(f"gip type: {type(gip)}")
    print(f"gip attrs: {gip.ncattrs()}")
    for attr in gip.ncattrs():
        print(f"  {attr} = {getattr(gip, attr)}")

# Check CMI
cmi = ds.variables['CMI']
print(f"CMI shape: {cmi.shape}, dtype: {cmi.dtype}")

ds.close()
