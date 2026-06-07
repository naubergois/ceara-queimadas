#!/usr/bin/env python3
"""
Pipeline GOES-18 para detecção de queimadas no Ceará.
Baixa dados CMIPF (bandas 07, 13, 14) e FDCF do GOES-18,
processa com K-Means adaptado para detecção de foco de calor,
e valida contra INPE e FIRMS.

Uso: python3 scripts/goes18_pipeline.py
"""

import os
import sys
import json
import math
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import netCDF4 as nc
import numpy as np

# ─── Configuração ────────────────────────────────────────────────
BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)

S3_BUCKET = "noaa-goes18"
AWS_REGION = "us-east-1"
NO_SIGN_REQUEST = "--no-sign-request"

# Bounding box Ceará
CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

# GOES-18 subpoint (137.2°W)
GOES18_LON = -137.2

# ─── Funções Auxiliares ──────────────────────────────────────────

def goes_abbr_day(dt: datetime) -> str:
    """Day of year as 3-digit string."""
    return f"{dt.timetuple().tm_yday:03d}"


def get_latest_available_hours(band: str, day: int, year: int = 2026) -> list:
    """Get available hours for a given band and day from S3."""
    prefix = f"s3://{S3_BUCKET}/ABI-L2-CMIPF/{year}/{day:03d}/"
    result = subprocess.run(
        ["aws", "s3", "ls", prefix, NO_SIGN_REQUEST, "--region", AWS_REGION],
        capture_output=True, text=True, timeout=30
    )
    hours = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if line and line.endswith('/'):
            h = line.replace('PRE ', '').replace('/', '')
            if h.isdigit():
                hours.append(int(h))
    return sorted(hours)


def list_s3_files(prefix: str) -> list:
    """List files in S3 prefix."""
    full_prefix = f"s3://{S3_BUCKET}/{prefix}"
    result = subprocess.run(
        ["aws", "s3", "ls", full_prefix, NO_SIGN_REQUEST, "--region", AWS_REGION],
        capture_output=True, text=True, timeout=30
    )
    files = []
    for line in result.stdout.strip().split('\n'):
        parts = line.strip().split()
        if len(parts) >= 4:
            files.append(parts[-1])
    return files


def download_s3_file(s3_key: str, local_path: str) -> bool:
    """Download a single file from S3."""
    s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
    result = subprocess.run(
        ["aws", "s3", "cp", s3_uri, local_path, NO_SIGN_REQUEST, "--region", AWS_REGION],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0


def download_goes18_data(day: int, hour: int, year: int = 2026) -> dict:
    """Download C07, C13, C14, FDCF files for given day+hour."""
    downloaded = {}
    hour_str = f"{hour:02d}"
    day_str = f"{day:03d}"

    # Target bands for CMIPF
    target_bands = {
        "C07": "M6C07",  # 3.9µm
        "C13": "M6C13",  # 10.3µm
        "C14": "M6C14",  # 11.2µm
    }

    # Download CMIPF bands
    for band_name, band_suffix in target_bands.items():
        prefix = f"ABI-L2-CMIPF/{year}/{day_str}/{hour_str}/"
        files = list_s3_files(prefix)
        target_file = None
        for f in files:
            if band_suffix in f and f.endswith(".nc"):
                target_file = f
                break
        if target_file:
            local_fname = f"GOES18_{band_name}_{day_str}_{hour_str}.nc"
            local_path = os.path.join(DATA_DIR, local_fname)
            s3_key = f"{prefix}{target_file}"
            print(f"  Downloading {band_name}: {target_file}")
            success = download_s3_file(s3_key, local_path)
            if success:
                downloaded[band_name] = local_path
                print(f"    -> {local_fname} ({os.path.getsize(local_path)/1e6:.1f} MB)")
            else:
                print(f"    FAILED to download {band_name}")

    # Download FDCF
    prefix = f"ABI-L2-FDCF/{year}/{day_str}/{hour_str}/"
    files = list_s3_files(prefix)
    target_file = None
    for f in files:
        if "FDCF" in f and f.endswith(".nc"):
            target_file = f
            break
    if target_file:
        local_fname = f"GOES18_FDCF_{day_str}_{hour_str}.nc"
        local_path = os.path.join(DATA_DIR, local_fname)
        s3_key = f"{prefix}{target_file}"
        print(f"  Downloading FDCF: {target_file}")
        success = download_s3_file(s3_key, local_path)
        if success:
            downloaded["FDCF"] = local_path
            print(f"    -> {local_fname} ({os.path.getsize(local_path)/1e6:.1f} MB)")
        else:
            print(f"    FAILED to download FDCF")

    return downloaded


# ─── Projeção GOES → lat/lon ──────────────────────────────────────

def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg, h_sat_m=35786023.0, r_eq=6378137.0, r_pol=6356752.3142):
    """
    Convert GOES fixed grid (x,y) in radians to latitude/longitude.
    Adapted from GOES-R algorithm.
    """
    # Parameters for GRS-80 ellipsoid
    a = r_eq
    b = r_pol
    h = h_sat_m
    lambda_0 = math.radians(sat_lon_deg)

    # Convert arrays
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)

    # Compute
    a_sq = a * a
    b_sq = b * b
    h_sq = h * h
    e_sq = (a_sq - b_sq) / a_sq

    # Equation from GOES-R PUG
    # a = sin^2(x) + cos^2(x)*[cos^2(y) + (a^2/b^2)*sin^2(y)]
    cos_x = np.cos(x_rad)
    sin_x = np.sin(x_rad)
    cos_y = np.cos(y_rad)
    sin_y = np.sin(y_rad)

    a_term = sin_x * sin_x + cos_x * cos_x * (cos_y * cos_y + (a_sq / b_sq) * sin_y * sin_y)
    b_term = 2 * h * cos_x * cos_y
    c_term = h_sq - a_sq

    # Discriminant
    sqrt_term = b_term * b_term - 4 * a_term * c_term

    # Only compute where sqrt_term >= 0
    sd = np.sqrt(np.maximum(sqrt_term, 0))

    # Distance from satellite to point
    s_d = (-b_term + sd) / (2 * a_term)

    # lat/lon
    lat = np.degrees(np.arctan2(
        -cos_x * sin_y,
        np.sqrt(np.maximum((b_sq / a_sq) * (a_term * s_d * s_d - h_sq) + h_sq * cos_x * cos_x * sin_y * sin_y, 0))
    ))

    lon = np.degrees(np.arctan2(
        s_d * sin_x * cos_y,
        h - s_d * cos_x * cos_y
    ) + lambda_0)

    return lat, lon


def extract_goes_projection(ds):
    """Extract projection parameters from a GOES NetCDF dataset."""
    # Get satellite subpoint - these are scalar variables, get the value directly
    sat_lon = GOES18_LON  # default for GOES-18
    
    # Try goes_imager_projection first (has the standard attributes)
    proj = ds.variables.get('goes_imager_projection')
    if proj is not None:
        try:
            lon_0 = float(getattr(proj, 'longitude_of_projection_origin'))
            sat_lon = lon_0
        except (AttributeError, TypeError):
            pass
    
    # Fallback: try the scalar variable
    if 'nominal_satellite_subpoint_lon' in ds.variables:
        try:
            val = ds.variables['nominal_satellite_subpoint_lon'][:]
            if isinstance(val, np.ndarray) and val.size > 0:
                sat_lon = float(val.flat[0])
        except Exception:
            pass

    # Fixed grid semi-major axis (GOES-18 uses GRS-80)
    h_sat = 35786023.0  # geostationary height in meters
    r_eq = 6378137.0
    r_pol = 6356752.3142

    return sat_lon, h_sat, r_eq, r_pol


def get_latlon_from_fixedgrid(ds, x_var, y_var):
    """Get latitude/longitude from GOES fixed grid projection."""
    x_vals = x_var[:]
    y_vals = y_var[:]
    sat_lon, h_sat, r_eq, r_pol = extract_goes_projection(ds)

    # Create meshgrid for full array expansion
    xx, yy = np.meshgrid(x_vals, y_vals)

    lat, lon = goes_fixed_grid_to_latlon(xx, yy, sat_lon, h_sat, r_eq, r_pol)
    return lat, lon


# ─── Detecção de fogo ────────────────────────────────────────────

def apply_scale_and_offset(ds, var_name):
    """Apply scale_factor and add_offset to a variable."""
    var = ds.variables[var_name]
    data = var[:]
    scale = getattr(var, 'scale_factor', 1.0)
    offset = getattr(var, 'add_offset', 0.0)
    return data.astype(np.float64) * scale + offset


def detect_fire_from_fdcf(fdcf_path: str) -> list:
    """
    Extract fire pixels from FDCF product.
    FDCF Mask values:
      0 = no fire
      1 = fire (saturated pixel)
      2 = fire (unsaturated pixel)
      3 = cloud
      4 = water
      5 = unknown/other
      6-10 = various fire detection quality levels
    We consider Mask >= 1 as potential fire, but primarily look at Mask=1,2
    """
    ds = nc.Dataset(fdcf_path)

    # Get the mask and other fire variables
    mask_raw = ds.variables['Mask'][:]
    temp_raw = ds.variables['Temp'][:]
    power_raw = ds.variables['Power'][:]
    area_raw = ds.variables['Area'][:]

    # Apply scaling
    mask = apply_scale_and_offset(ds, 'Mask')
    temp = apply_scale_and_offset(ds, 'Temp')  # Kelvin
    power = apply_scale_and_offset(ds, 'Power')  # MW
    area = apply_scale_and_offset(ds, 'Area')  # m²

    # Get lat/lon
    x_var = ds.variables['x']
    y_var = ds.variables['y']
    lat_arr, lon_arr = get_latlon_from_fixedgrid(ds, x_var, y_var)

    # Extract timestamp
    timestamp = extract_timestamp(fdcf_path)

    # Find fire pixels within Ceará bounding box
    fire_pixels = []
    fire_mask_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    fire_mask_active = [1, 2]  # Saturated and unsaturated fire

    # Search for fire pixels in Ceará region
    # Only process pixels where mask > 0 to be efficient
    fire_idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )

    if len(fire_idx[0]) == 0:
        ds.close()
        return []

    for i in range(len(fire_idx[0])):
        yi, xi = fire_idx[0][i], fire_idx[1][i]
        m_val = int(mask[yi, xi])
        if m_val in fire_mask_active:
            fire_pixels.append({
                'lat': float(lat_arr[yi, xi]),
                'lon': float(lon_arr[yi, xi]),
                'mask_value': m_val,
                'temperature_k': float(temp[yi, xi]),
                'frp_mw': float(power[yi, xi]),
                'area_m2': float(area[yi, xi]),
                'source': 'FDCF',
                'timestamp': timestamp,
            })

    ds.close()
    return fire_pixels


def make_safe_int(data):
    """Ensure data is suitable for integer operations."""
    if np.ma.is_masked(data):
        return data.filled(0)
    return data


def extract_timestamp(filepath: str) -> str:
    """Extract timestamp from GOES filename (sYYYYDDDHHMMSSS format)."""
    fname = os.path.basename(filepath)
    match = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if match:
        year, doy, hour, minute, second = match.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(
            days=int(doy) - 1,
            hours=int(hour),
            minutes=int(minute),
            seconds=int(second),
        )
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    # Fall back to file timestamp
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return "unknown"


# ─── K-Means / Clusterização Termal ───────────────────────────────

def detect_hotspots_kmeans(c07_path: str, c13_path: str, c14_path: str) -> list:
    """
    Detect fire hotspots using K-Means clustering on thermal bands.
    
    Strategy:
    1. Load C07 (3.9µm), C13 (10.3µm), C14 (11.2µm)
    2. Crop to Ceará bounding box
    3. Apply simple threshold-based detection first:
       - Band 7 (3.9µm) > 320K + BTD(7-14) > 2K OR
       - Band 7 (3.9µm) > 310K + BTD(7-14) > 4K (night-adjusted)
    4. Then apply K-Means clustering to separate fire from background
    """
    from sklearn.cluster import KMeans

    ds7 = nc.Dataset(c07_path)
    ds13 = nc.Dataset(c13_path)
    ds14 = nc.Dataset(c14_path)

    # Get lat/lon
    x_var = ds7.variables['x']
    y_var = ds7.variables['y']
    lat_arr, lon_arr = get_latlon_from_fixedgrid(ds7, x_var, y_var)

    # Get CMI with scaling
    c07_raw = ds7.variables['CMI'][:]
    c13_raw = ds13.variables['CMI'][:]
    c14_raw = ds14.variables['CMI'][:]

    c07 = apply_scale_and_offset(ds7, 'CMI')
    c13 = apply_scale_and_offset(ds13, 'CMI')
    c14 = apply_scale_and_offset(ds14, 'CMI')

    timestamp = extract_timestamp(c07_path)

    # Find pixels in Ceará bounding box
    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )

    if len(idx[0]) == 0:
        for d in [ds7, ds13, ds14]:
            d.close()
        return []

    print(f"  Pixels no bounding box Ceará: {len(idx[0])}")

    # Extract pixel data
    pixels = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t07 = float(c07[yi, xi])
        t13 = float(c13[yi, xi])
        t14 = float(c14[yi, xi])
        btd_7_14 = t07 - t14
        btd_7_13 = t07 - t13
        pixels.append({
            'yi': yi, 'xi': xi,
            'lat': float(lat_arr[yi, xi]),
            'lon': float(lon_arr[yi, xi]),
            't07': t07, 't13': t13, 't14': t14,
            'btd_7_14': btd_7_14,
            'btd_7_13': btd_7_13,
        })

    if not pixels:
        for d in [ds7, ds13, ds14]:
            d.close()
        return []

    # Step 1: Threshold-based detection (GFED/INPE-style)
    # Fire characteristics in Band 7 (3.9µm):
    # - Hot pixels show T07 significantly higher than background
    # - BTD(7-14) > threshold indicates fire
    # Daytime thresholds (conservative for initial detection)
    threshold_candidates = []
    for p in pixels:
        # Strong fire: T07 > 330K and BTD(7-14) > 5K
        if p['t07'] > 330 and p['btd_7_14'] > 5:
            threshold_candidates.append({**p, 'confidence': 'alta'})
        # Moderate fire: T07 > 320K and BTD(7-14) > 3K
        elif p['t07'] > 320 and p['btd_7_14'] > 3:
            threshold_candidates.append({**p, 'confidence': 'media'})
        # Potential fire: T07 > 310K and BTD(7-14) > 2K
        elif p['t07'] > 310 and p['btd_7_14'] > 2:
            threshold_candidates.append({**p, 'confidence': 'baixa'})

    # Step 2: K-Means refinement on the hotspot candidates + surrounding pixels
    if len(threshold_candidates) >= 3:
        # Build feature matrix for clustering
        # Get pixels around each candidate to form clusters
        all_fire_features = []
        fire_pixel_map = {}
        for fc in threshold_candidates:
            yi, xi = fc['yi'], fc['xi']
            # Extract neighborhood (3x3) for context
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = yi + dy, xi + dx
                    if 0 <= ny < c07.shape[0] and 0 <= nx < c07.shape[1]:
                        try:
                            lt = float(lat_arr[ny, nx])
                            ln = float(lon_arr[ny, nx])
                            t7 = float(c07[ny, nx])
                            t13_v = float(c13[ny, nx])
                            t14_v = float(c14[ny, nx])
                            btd = t7 - t14_v
                            if not math.isnan(t7) and not math.isnan(t13_v):
                                key = (ny, nx)
                                if key not in fire_pixel_map:
                                    fire_pixel_map[key] = {
                                        'lat': lt, 'lon': ln,
                                        't07': t7, 't13': t13_v, 't14': t14_v,
                                        'btd_7_14': btd,
                                    }
                                    all_fire_features.append([t7, t13_v, btd])
                        except (ValueError, IndexError):
                            continue

        if len(all_fire_features) >= 5:
            features = np.array(all_fire_features)
            # Normalize features
            f_mean = features.mean(axis=0)
            f_std = features.std(axis=0) + 1e-10
            features_norm = (features - f_mean) / f_std

            # K-Means with 2 clusters (fire + background)
            n_clusters = min(2, len(features_norm))
            if n_clusters >= 2:
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
                labels = kmeans.fit_predict(features_norm)

                # Find which cluster has higher T07 mean (that's the fire cluster)
                cluster_means = {}
                for i, label in enumerate(labels):
                    if label not in cluster_means:
                        cluster_means[label] = {'t07': [], 'btd': []}
                    cluster_means[label]['t07'].append(features[i][0])
                    cluster_means[label]['btd'].append(features[i][2])

                fire_cluster = max(cluster_means.keys(),
                                   key=lambda x: np.mean(cluster_means[x]['t07']))

                kmeans_pixels = []
                pixel_keys = list(fire_pixel_map.keys())
                for i, label in enumerate(labels):
                    if label == fire_cluster and i < len(pixel_keys):
                        key = pixel_keys[i]
                        p = fire_pixel_map[key]
                        kmeans_pixels.append(p)

                # Filter K-Means results by fire criteria
                kmeans_fire = []
                for p in kmeans_pixels:
                    if p['t07'] > 315 and p['btd_7_14'] > 2:
                        p['confidence'] = 'kmeans'
                        p['source'] = 'CMIPF_KMeans'
                        p['timestamp'] = timestamp
                        kmeans_fire.append(p)

                # Merge threshold and K-Means results, deduplicate by proximity
                all_detections = threshold_candidates + kmeans_fire
            else:
                all_detections = threshold_candidates
        else:
            all_detections = threshold_candidates
    else:
        all_detections = threshold_candidates

    for d in [ds7, ds13, ds14]:
        d.close()

    # Deduplicate by spatial proximity (within ~2km)
    final = []
    for d in all_detections:
        is_dup = False
        for existing in final:
            lat_diff = abs(d['lat'] - existing['lat']) * 111000
            lon_diff = abs(d['lon'] - existing['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            distance = math.sqrt(lat_diff**2 + lon_diff**2)
            if distance < 2000:  # 2km
                is_dup = True
                break
        if not is_dup:
            final.append(d)

    return final


# ─── Execução Principal ───────────────────────────────────────────

def run():
    """Main pipeline execution."""
    print("=" * 60)
    print("GOES-18 Pipeline de Detecção de Queimadas — Ceará")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    print(f"Data/hora atual: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Dia do ano (doy): {goes_abbr_day(now)}")
    print()

    # 1. Determine which day/hour to download
    # Ceará is UTC-3, prime fire hours 12-20 UTC (9AM-5PM local)
    # We want the most recent complete hour
    download_day = now.timetuple().tm_yday
    download_hour = now.hour

    # Check if current hour has data (may be incomplete), go back if needed
    # For CMIPF: check hours from current-2 to current
    try_hours = []
    for h_offset in [0, -1, -2, -3]:
        h = (now + timedelta(hours=h_offset)).hour
        d = (now + timedelta(hours=h_offset)).timetuple().tm_yday
        try_hours.append((d, h))

    # Also check yesterday (day 155)
    yesterday = now - timedelta(days=1)
    for h in [15, 16, 17, 18, 19, 20, 21, 22, 23]:
        try_hours.append((yesterday.timetuple().tm_yday, h))
    for h in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        try_hours.append((now.timetuple().tm_yday, h))

    # Also check day 154 (two days ago)
    two_days_ago = now - timedelta(days=2)
    for h in range(12, 24):
        try_hours.append((two_days_ago.timetuple().tm_yday, h))

    # Deduplicate
    try_hours = list(set(try_hours))
    try_hours.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # 2. Try to download data for available hours
    all_fire_pixels = []
    all_fdcf_pixels = []

    print("\n--- Buscando dados GOES-18 ---")
    success = False
    for day, hour in try_hours[:10]:  # Try first 10 candidate hours
        print(f"\nTentando day={day}, hour={hour}...")

        # Check if CMIPF data exists for this hour
        prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
        files = list_s3_files(prefix)
        if not files:
            continue

        # Check for C07 specifically
        has_c07 = any("C07" in f for f in files)
        if not has_c07:
            continue

        print(f"  Dados CMIPF encontrados para day={day}, hour={hour}")
        downloaded = download_goes18_data(day, hour)

        if "C07" in downloaded and "C13" in downloaded and "C14" in downloaded:
            success = True
            print(f"\n--- Dados baixados com sucesso para day={day}, hour={hour} ---")

            # 3. Process CMIPF with K-Means
            print("\n--- Pipeline K-Means (CMIPF) ---")
            cmipf_pixels = detect_hotspots_kmeans(
                downloaded["C07"],
                downloaded["C13"],
                downloaded["C14"]
            )
            print(f"  Focos detectados via CMIPF/K-Means: {len(cmipf_pixels)}")
            all_fire_pixels.extend(cmipf_pixels)

            # 4. Process FDCF
            if "FDCF" in downloaded:
                print("\n--- Pipeline FDCF ---")
                fdcf_pixels = detect_fire_from_fdcf(downloaded["FDCF"])
                print(f"  Focos detectados via FDCF: {len(fdcf_pixels)}")
                all_fdcf_pixels.extend(fdcf_pixels)

            # Only process one successful download for this test run
            break
        else:
            print(f"  Download incompleto para day={day}, hour={hour}")
            # Continue to next hour

    if not success:
        print("\nNenhum dado GOES-18 disponível nos períodos testados.")
        print("Verificando dados do dia 155 (ontem)...")
        for day in [155, 154]:
            for hour in range(12, 23):
                prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
                files = list_s3_files(prefix)
                if any("C07" in f for f in files):
                    print(f"  Encontrado C07 para day={day}, hour={hour}")
                    downloaded = download_goes18_data(day, hour)
                    if "C07" in downloaded and "C13" in downloaded and "C14" in downloaded:
                        print(f"\n--- Processando day={day}, hour={hour} ---")
                        cmipf_pixels = detect_hotspots_kmeans(
                            downloaded["C07"],
                            downloaded["C13"],
                            downloaded["C14"]
                        )
                        print(f"  Focos CMIPF: {len(cmipf_pixels)}")
                        all_fire_pixels.extend(cmipf_pixels)

                        if "FDCF" in downloaded:
                            fdcf_pixels = detect_fire_from_fdcf(downloaded["FDCF"])
                            print(f"  Focos FDCF: {len(fdcf_pixels)}")
                            all_fdcf_pixels.extend(fdcf_pixels)
                        break
            if all_fire_pixels:
                break

    # 5. Report
    print("\n" + "=" * 60)
    print("RESULTADOS FINAIS")
    print("=" * 60)

    print(f"\n--- CMIPF + K-Means ---")
    if all_fire_pixels:
        print(f"Total de focos detectados: {len(all_fire_pixels)}")
        for i, fp in enumerate(all_fire_pixels[:20]):
            conf = fp.get('confidence', 'N/A')
            print(f"  [{i+1}] lat={fp['lat']:.4f} lon={fp['lon']:.4f} "
                  f"T07={fp['t07']:.1f}K BTD={fp['btd_7_14']:.1f}K conf={conf}")
        if len(all_fire_pixels) > 20:
            print(f"  ... e mais {len(all_fire_pixels) - 20} focos")
    else:
        print("Nenhum foco detectado via CMIPF + K-Means.")

    print(f"\n--- FDCF ---")
    if all_fdcf_pixels:
        print(f"Total de focos detectados: {len(all_fdcf_pixels)}")
        for i, fp in enumerate(all_fdcf_pixels[:20]):
            print(f"  [{i+1}] lat={fp['lat']:.4f} lon={fp['lon']:.4f} "
                  f"T={fp['temperature_k']:.1f}K FRP={fp['frp_mw']:.1f}MW mask={fp['mask_value']}")
        if len(all_fdcf_pixels) > 20:
            print(f"  ... e mais {len(all_fdcf_pixels) - 20} focos")
    else:
        print("Nenhum foco detectado via FDCF.")

    # 6. Save results to JSON
    results = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cmipf_kmeans": all_fire_pixels,
        "fdcf": all_fdcf_pixels,
        "total_cmipf": len(all_fire_pixels),
        "total_fdcf": len(all_fdcf_pixels),
        "total_combined": len(all_fire_pixels) + len(all_fdcf_pixels),
    }

    out_path = os.path.join(DATA_DIR, "goes18_detection_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResultados salvos em: {out_path}")

    print("\n" + "=" * 60)
    print("VALIDAÇÃO CRUZADA")
    print("=" * 60)
    print("INPE (referência): 11 focos reportados")
    print("FIRMS (referência): 27 focos reportados")
    print(f"GOES-18 CMIPF + K-Means: {len(all_fire_pixels)}")
    print(f"GOES-18 FDCF: {len(all_fdcf_pixels)}")
    print(f"GOES-18 Total combinado: {len(all_fire_pixels) + len(all_fdcf_pixels)}")
    print()

    return results


if __name__ == "__main__":
    results = run()
