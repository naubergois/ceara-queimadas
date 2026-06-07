#!/usr/bin/env python3
"""Analyze GOES-19 FDCF product for fire detection in Ceara."""
import sys, os, json, math, re
from datetime import datetime, timezone, timedelta
import netCDF4 as nc
import numpy as np

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25


def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a, b, h = 6378137.0, 6356752.31414, 35786023.0
    lambda_0 = math.radians(sat_lon_deg)
    x = np.array(x_arr, dtype=np.float64)
    y = np.array(y_arr, dtype=np.float64)
    cos_x, sin_x = np.cos(x), np.sin(x)
    cos_y, sin_y = np.cos(y), np.sin(y)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    B = -2.0*h*cos_x*cos_y
    c_term = h_sq - a_sq
    sd = np.sqrt(np.maximum(B*B - 4*a_term*c_term, 0))
    s_d = (-B - sd)/(2*a_term)
    lat = np.degrees(np.arctan2(-cos_x*sin_y, np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq)*sin_x**2*sin_y**2, 0))))
    lon = np.degrees(lambda_0 + np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y))
    return lat, lon


def extract_ts(fpath):
    fname = os.path.basename(fpath)
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', fname)
    if m:
        y, d, h, mi, s = m.groups()
        dt = datetime(int(y), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(d)-1, hours=int(h), minutes=int(mi), seconds=int(s))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return 'unknown'


fdcf_path = os.path.join(BASE, 'OR_ABI-L2-FDCF-M6_G19_s20261571420216_e20261571429524_c20261571430041.nc')
if not os.path.exists(fdcf_path):
    print("ERROR: FDCF file not found")
    sys.exit(1)

print(f'FDCF file: {os.path.getsize(fdcf_path)/1e6:.1f} MB')

ds = nc.Dataset(fdcf_path)
print(f'Variables: {list(ds.variables.keys())}')

fdcf_lon = -75.0
proj = None
if 'goes_imager_projection' in ds.variables:
    proj = ds.variables['goes_imager_projection']
if proj is not None:
    try:
        fdcf_lon = float(getattr(proj, 'longitude_of_projection_origin', -75.0))
        if fdcf_lon == 0.0: fdcf_lon = -75.0
        print(f'Satellite longitude from file: {fdcf_lon:.1f}°')
    except:
        pass

x = ds.variables['x'][:]
y = ds.variables['y'][:]
lat_arr, lon_arr = goes_fixed_grid_to_latlon(np.meshgrid(x, y)[0], np.meshgrid(x, y)[1], fdcf_lon)

# Process DQF
dqf = ds.variables['DQF'][:]
dqf_data = dqf.filled(255) if hasattr(dqf, 'filled') else np.array(dqf)

# Also try Temp and Power
temp_var = ds.variables.get('Temp')
power_var = ds.variables.get('Power')
area_var = ds.variables.get('Area')

print(f'DQF shape: {dqf_data.shape}')
print(f'DQF unique values: {np.unique(dqf_data).tolist()}')

# Count fire pixels (DQF == 0 = good fire pixel)
fire_mask = dqf_data == 0
total_fire = np.sum(fire_mask)
print(f'Total fire pixels (DQF==0): {total_fire}')

# Apply Ceará mask on fire pixels
ce_idx = np.where(
    fire_mask &
    (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
    (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
)
print(f'Fire pixels in Ceará: {len(ce_idx[0])}')

if len(ce_idx[0]) > 0:
    temp_data = ds.variables['Temp'][:]
    temp_scale = getattr(ds.variables['Temp'], 'scale_factor', 1)
    temp_offset = getattr(ds.variables['Temp'], 'add_offset', 0)
    
    power_data = ds.variables['Power'][:].filled(0) if hasattr(ds.variables['Power'][:], 'filled') else ds.variables['Power'][:]
    power_scale = getattr(ds.variables['Power'], 'scale_factor', 1)
    power_offset = getattr(ds.variables['Power'], 'add_offset', 0)
    
    area_data = ds.variables['Area'][:].filled(0) if hasattr(ds.variables['Area'][:], 'filled') else ds.variables['Area'][:]
    area_scale = getattr(ds.variables['Area'], 'scale_factor', 1)
    area_offset = getattr(ds.variables['Area'], 'add_offset', 0)
    
    print('\n=== FDCF FIRE DETECTIONS IN CEARÁ ===')
    for i in range(len(ce_idx[0])):
        yi, xi = ce_idx[0][i], ce_idx[1][i]
        t_k = float(temp_data[yi, xi]) * temp_scale + temp_offset if not np.ma.is_masked(temp_data[yi, xi]) else 0
        fp = float(power_data[yi, xi]) * power_scale + power_offset if power_scale and not np.ma.is_masked(power_data[yi, xi]) else 0
        a_m2 = float(area_data[yi, xi]) * area_scale + area_offset if area_scale and not np.ma.is_masked(area_data[yi, xi]) else 0
        print(f'  ({float(lat_arr[yi,xi]):.4f}, {float(lon_arr[yi,xi]):.4f}) T={t_k:.1f}K FRP={fp:.1f}MW Area={a_m2:.0f}m²')
else:
    print('No FDCF fire pixels in Ceará')

ts = extract_ts(fdcf_path)
print(f'\nTimestamp: {ts}')

ds.close()
print('DONE')
