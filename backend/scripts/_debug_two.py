#!/usr/bin/env python3
"""Process one scan to test coordinate conversion."""
import sys, os, math, numpy as np
import netCDF4 as nc

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
GOES19_LON = -75.0

# Replicate cron_analysis.py's exact approach
def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg):
    a = 6378137.0
    b = 6356752.31414
    h = 35786023.0
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
        np.sqrt(np.maximum(cos_y**2 + (a_sq/b_sq) * sin_x**2 * sin_y**2, 0))
    ))
    lon = np.degrees(
        lambda_0 + np.arctan2(s_d * sin_x * cos_y, h - s_d * cos_x * cos_y)
    )
    return lat, lon

c07_path = os.path.join(BASE, sorted([f for f in os.listdir(BASE) if f.startswith('OR_ABI-L2-CMIPF-M6C07') and '2026157' in f])[0])
ds = nc.Dataset(c07_path)
x_var = ds.variables['x']
y_var = ds.variables['y']

# Use meshgrid exactly like cron_analysis.py
X_grid, Y_grid = np.meshgrid(x_var[:], y_var[:])
print(f"X_grid shape: {X_grid.shape}, Y_grid shape: {Y_grid.shape}")

lat_arr, lon_arr = goes_fixed_grid_to_latlon(X_grid, Y_grid, GOES19_LON)
print(f"lat_arr shape: {lat_arr.shape}, lon_arr shape: {lon_arr.shape}")
print(f"lat range: {np.min(lat_arr):.2f} to {np.max(lat_arr):.2f}")
print(f"lon range: {np.min(lon_arr):.2f} to {np.max(lon_arr):.2f}")

# Check Ceará
CEARA_LAT_MIN, CEARA_LAT_MAX, CEARA_LON_MIN, CEARA_LON_MAX = -7.85, -2.78, -41.42, -37.25
idx = np.where(
    (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
    (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
)
print(f"Ceará pixels: {len(idx[0])}")

# Verify a few sample coordinates
for i in range(min(5, len(idx[0]))):
    yi, xi = idx[0][i], idx[1][i]
    print(f"  ({lat_arr[yi, xi]:.4f}, {lon_arr[yi, xi]:.4f})")

ds.close()
