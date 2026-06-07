#!/usr/bin/env python3
"""Extract GOES-19 FDCF fire pixels over Ceará - corrected fire mask values."""
import os, json, math
import netCDF4 as nc
import numpy as np

BASE = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data'
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

fpath = os.path.join(BASE, "OR_ABI-L2-FDCF-M6_G19_s20261571420216_e20261571429524_c20261571430041.nc")
ds = nc.Dataset(fpath)

sat_lon = float(ds.variables['nominal_satellite_subpoint_lon'][:])
print(f"Satellite: GOES-19 at {sat_lon:.1f}°")
total_fires = int(ds['total_number_of_pixels_with_fires_detected'][:])
print(f"Total fires detected globally: {total_fires}")

# Mask interpretation (GOES-R FDCF):
# -99 = Fill/No data
# 10-35 = Cloud types
# 40 = Water
# 50 = Coastal/shadow
# 60 = Land/snow
# 100 = Nominal fire processing
# 126-127 = Glint
# 150-170 = Various cloud
# 200 = Fire (land)
# 201 = Fire (water)
# 215 = Fire (high confidence)
# 220 = Fire (saturated)
# 240-245 = Other

FIRE_VALUES = {200, 201, 215, 220}
mask = np.array(ds['Mask'][:], dtype=int)
if hasattr(mask, 'mask') and np.ma.is_masked(mask):
    mask = mask.data

# Check for fires
for v in sorted(set(mask.flat)):
    cnt = int(np.sum(mask == v))
    if cnt > 0:
        label = ""
        if v in FIRE_VALUES: label = " 🔥 FIRE"
        elif v >= 200: label = " (high temp)"
        if cnt < 5000 or v >= 200:
            print(f"  Mask={v}: {cnt} pixels{label}")

# Get fire pixels
fire_mask = np.isin(mask, list(FIRE_VALUES))
print(f"\nFire pixels (values 200/201/215/220): {np.sum(fire_mask)}")

# Get x,y and compute lat/lon
x_arr = ds['x'][:].astype(float)
y_arr = ds['y'][:].astype(float)
a, b, h = 6378137.0, 6356752.31414, 35786023.0
lambda_0 = math.radians(sat_lon)
x_rad = np.meshgrid(x_arr, y_arr)[0] / h
y_rad = np.meshgrid(x_arr, y_arr)[1] / h
cos_x = np.cos(x_rad); sin_x = np.sin(x_rad)
cos_y = np.cos(y_rad); sin_y = np.sin(y_rad)
a_sq, b_sq, h_sq = a*a, b*b, h*h
a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
B_val = -2.0*h*cos_x*cos_y
c_term = h_sq - a_sq
s_d = (-B_val - np.sqrt(np.maximum(B_val*B_val - 4*a_term*c_term, 0))) / (2*a_term)
lat = np.degrees(np.arctan2(-cos_x*sin_y, np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq)*sin_x**2*sin_y**2, 0))))
lon = np.degrees(lambda_0 + np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y))

# Filter fires over Ceará
ce_idx = (lat >= CEARA_LAT_MIN) & (lat <= CEARA_LAT_MAX) & (lon >= CEARA_LON_MIN) & (lon <= CEARA_LON_MAX)
fire_ce = fire_mask & ce_idx
fire_idx = np.where(fire_ce)
print(f"Fire pixels over Ceará: {len(fire_idx[0])}")

ceara_fires = []
for i in range(len(fire_idx[0])):
    yi, xi = fire_idx[0][i], fire_idx[1][i]
    area_val = float(ds['Area'][yi, xi]) if np.isscalar(ds['Area'][yi, xi]) else float(np.array(ds['Area'][yi, xi]))
    temp_val = float(ds['Temp'][yi, xi]) if np.isscalar(ds['Temp'][yi, xi]) else float(np.array(ds['Temp'][yi, xi]))
    power_val = float(ds['Power'][yi, xi]) if np.isscalar(ds['Power'][yi, xi]) else float(np.array(ds['Power'][yi, xi]))
    fire_entry = {
        'lat': round(float(lat[yi, xi]), 4),
        'lon': round(float(lon[yi, xi]), 4),
        'mask_val': int(mask[yi, xi]),
        'power_MW': round(power_val, 2),
    }
    if temp_val > 0 and temp_val < 10000:
        fire_entry['temp_K'] = round(temp_val, 1)
    if area_val > 0 and area_val < 1e9:
        fire_entry['area_m2'] = round(area_val * 10000, 1)
    ceara_fires.append(fire_entry)

if ceara_fires:
    ceara_fires.sort(key=lambda x: x['power_MW'], reverse=True)
    print(f"Top fires in Ceará (by power):")
    for f in ceara_fires[:10]:
        t_str = f" | {f.get('temp_K', '?')}K" if 'temp_K' in f else ""
        a_str = f" | {f.get('area_m2', '?')}m²" if 'area_m2' in f else ""
        print(f"  {f['lat']},{f['lon']} | Mask={f['mask_val']} | {f['power_MW']:.1f}MW{t_str}{a_str}")
else:
    print("Nenhum foco de fogo no Ceará neste scan.")

# Show global fires by region
for mval in sorted(set(mask.flat)):
    if mval in FIRE_VALUES:
        cnt = int(np.sum(mask == mval))
        m_lat = lat[mask == mval]
        m_lon = lon[mask == mval]
        print(f"  Global fires mask={mval}: {cnt} pixels, lat range: {np.min(m_lat):.1f} to {np.max(m_lat):.1f}")

out = {
    'timestamp': '2026-06-06 14:20 UTC',
    'satellite': 'GOES-19',
    'sat_lon': float(sat_lon),
    'global_fires': total_fires,
    'ceara_fire_count': len(ceara_fires),
    'ceara_fires': ceara_fires[:50],
}
with open(os.path.join(BASE, 'fdcf_ceara_doy157.json'), 'w') as f:
    json.dump(out, f, indent=2)
print(f"\nSaved to fdcf_ceara_doy157.json")
ds.close()
