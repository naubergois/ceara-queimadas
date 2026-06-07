#!/usr/bin/env python3
"""Scan GOES-19 FDCF for DOY 157 (today) fires over Ceará."""
import os, json, math, re
from datetime import datetime, timedelta, timezone
import netCDF4 as nc
import numpy as np

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a = 6378137.0; b = 6356752.31414; h = 35786023.0
    lambda_0 = math.radians(sat_lon_deg)
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)
    cos_x = np.cos(x_rad); sin_x = np.sin(x_rad)
    cos_y = np.cos(y_rad); sin_y = np.sin(y_rad)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    B = -2.0*h*cos_x*cos_y
    c_term = h_sq - a_sq
    discriminant = B*B - 4*a_term*c_term
    sd = np.sqrt(np.maximum(discriminant, 0))
    s_d = (-B - sd)/(2*a_term)
    lat = np.degrees(np.arctan2(
        -cos_x * sin_y,
        np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq) * sin_x**2 * sin_y**2, 0))))
    lon = np.degrees(lambda_0 + np.arctan2(s_d * sin_x * cos_y, h - s_d * cos_x * cos_y))
    return lat, lon

# Find all FDCF files for DOY 157 (G19 standard)
fdcf_files = []
for f in os.listdir(BASE):
    m = re.search(r'OR_ABI-L2-FDCF-M6_G19_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', f)
    if m:
        year, doy, hour, minute, second = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        dt = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=doy-1, hours=hour, minutes=minute, seconds=second)
        fdcf_files.append((dt, os.path.join(BASE, f)))
    # Also check legacy naming
    m2 = re.search(r'GOES1[89]_FDCF_(\d{3})_(\d{2})\.nc', f)
    if m2:
        doy, hour = int(m2.group(1)), int(m2.group(2))
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=doy-1, hours=hour)
        fdcf_files.append((dt, os.path.join(BASE, f)))

fdcf_files.sort(key=lambda x: x[0])
print(f"FDCF files found: {len(fdcf_files)}")
for dt, path in fdcf_files:
    print(f"  {dt.strftime('%Y-%m-%d %H:%M UTC')}: {os.path.basename(path)}")

# Process LATEST FDCF file for DOY 157
latest = [x for x in fdcf_files if x[0].year == 2026 and x[0].timetuple().tm_yday == 157]
if latest:
    dt, fpath = latest[-1]
    print(f"\nProcessing latest DOY157 FDCF: {dt}")
    print(f"File: {os.path.basename(fpath)}")
    ds = nc.Dataset(fpath)
    
    # Determine variable
    var_name = None
    for v in ['FDCF', 'FireMask']:
        if v in ds.variables:
            var_name = v
            break
    
    if var_name:
        data = ds.variables[var_name][:]
        print(f"Variable: {var_name}, shape: {data.shape}, dtype: {data.dtype}")
        
        # Get coordinates
        if 'x' in ds.variables and 'y' in ds.variables:
            x_arr = ds.variables['x'][:]
            y_arr = ds.variables['y'][:]
            print(f"x: {len(x_arr)}, y: {len(y_arr)}")
            
            sat_lon = -75.2
            if 'goes_imager_projection' in ds.variables:
                proj = ds.variables['goes_imager_projection']
                try: sat_lon = float(getattr(proj, 'longitude_of_projection_origin'))
                except: pass
            
            lat_arr, lon_arr = goes_fixed_grid_to_latlon(
                np.meshgrid(x_arr, y_arr)[0],
                np.meshgrid(x_arr, y_arr)[1],
                sat_lon)
            
            # FDCF values: 0=no fire, 1=intensive fire, 2=extensive fire, etc.
            fire_pixels_mask = data > 0
            if hasattr(data, 'mask') and np.ma.is_masked(data):
                fire_pixels_mask = (~data.mask) & (data > 0)
            
            fire_indices = np.where(fire_pixels_mask)
            print(f"Total fire pixels (all): {len(fire_indices[0])}")
            
            # Filter for Ceará
            ceara_fires = []
            for i in range(len(fire_indices[0])):
                yi, xi = fire_indices[0][i], fire_indices[1][i]
                lat, lon = float(lat_arr[yi, xi]), float(lon_arr[yi, xi])
                if CEARA_LAT_MIN <= lat <= CEARA_LAT_MAX and CEARA_LON_MIN <= lon <= CEARA_LON_MAX:
                    ceara_fires.append({
                        'lat': round(lat, 4),
                        'lon': round(lon, 4),
                        'val': int(data[yi, xi])
                    })
            
            print(f"Fire pixels in Ceará: {len(ceara_fires)}")
            if ceara_fires:
                print("Top 10 (by lat):")
                for f in sorted(ceara_fires, key=lambda x: x['lat'])[:10]:
                    print(f"  {f['lat']}, {f['lon']} (val={f['val']})")
                
                # Log to JSON
                out = {
                    'timestamp': dt.strftime('%Y-%m-%d %H:%M UTC'),
                    'satellite': 'GOES-19',
                    'sat_lon': sat_lon,
                    'total_fire_pixels_all': len(fire_indices[0]),
                    'fire_pixels_ceara': len(ceara_fires),
                    'fires': ceara_fires
                }
                with open(os.path.join(BASE, 'fdcf_ceara_doy157.json'), 'w') as f:
                    json.dump(out, f, indent=2)
                print(f"\nSaved to fdcf_ceara_doy157.json")
            else:
                print("Nenhum foco no Ceará neste scan FDCF.")
        else:
            print("No x/y variables found")
    else:
        print("Neither FDCF nor FireMask found")
    ds.close()
else:
    print("No DOY157 FDCF files found")
