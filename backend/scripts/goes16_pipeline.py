#!/usr/bin/env python3
"""
GOES-16 Pipeline de Detecção de Queimadas — Ceará (versão corrigida)
GOES-16 está em 75.2°W → cobre a América do Sul e o Ceará.
GOES-18 (137°W) → cobre o Pacífico, NÃO cobre o Ceará.
"""
import os, sys, json, math, re, subprocess
from datetime import datetime, timedelta, timezone
import netCDF4 as nc
import numpy as np
from sklearn.cluster import KMeans

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

S3_BUCKET = "noaa-goes16"
GOES16_LON = -75.2

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25


def s3_ls(prefix: str) -> list:
    full = f"s3://{S3_BUCKET}/{prefix}"
    r = subprocess.run(["aws", "s3", "ls", full, "--no-sign-request", "--region", "us-east-1"],
                       capture_output=True, text=True, timeout=30)
    files = []
    for line in r.stdout.strip().split("\n"):
        line = line.strip()
        if line.endswith(".nc"):
            parts = line.split()
            if parts:
                files.append(parts[-1])
    return files


def s3_download(s3_key: str, local: str) -> bool:
    uri = f"s3://{S3_BUCKET}/{s3_key}"
    r = subprocess.run(["aws", "s3", "cp", uri, local, "--no-sign-request", "--region", "us-east-1"],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def goes_fixed_grid_to_latlon(x_arr, y_arr, sat_lon_deg,
                                h_sat_m=35786023.0, r_eq=6378137.0, r_pol=6356752.3142):
    a, b, h = r_eq, r_pol, h_sat_m
    lambda_0 = math.radians(sat_lon_deg)
    x_rad = np.array(x_arr, dtype=np.float64)
    y_rad = np.array(y_arr, dtype=np.float64)
    a_sq, b_sq, h_sq = a*a, b*b, h*h
    e_sq = (a_sq - b_sq) / a_sq
    cos_x, sin_x = np.cos(x_rad), np.sin(x_rad)
    cos_y, sin_y = np.cos(y_rad), np.sin(y_rad)
    a_term = sin_x*sin_x + cos_x*cos_x*(cos_y*cos_y + (a_sq/b_sq)*sin_y*sin_y)
    b_term = 2*h*cos_x*cos_y
    c_term = h_sq - a_sq
    sqrt_term = b_term*b_term - 4*a_term*c_term
    sd = np.sqrt(np.maximum(sqrt_term, 0))
    s_d = (-b_term + sd) / (2*a_term)
    lat = np.degrees(np.arctan2(
        -cos_x*sin_y,
        np.sqrt(np.maximum((b_sq/a_sq)*(a_term*s_d*s_d - h_sq) + h_sq*cos_x*cos_x*sin_y*sin_y, 0))
    ))
    lon = np.degrees(np.arctan2(s_d*sin_x*cos_y, h - s_d*cos_x*cos_y) + lambda_0)
    return lat, lon


def apply_scale(ds, var_name):
    v = ds.variables[var_name]
    data = v[:]
    scale = getattr(v, 'scale_factor', 1.0)
    offset = getattr(v, 'add_offset', 0.0)
    return data.astype(np.float64) * scale + offset


def extract_timestamp(filepath: str) -> str:
    fname = os.path.basename(filepath)
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hr), minutes=int(mi), seconds=int(sc))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return "unknown"


def download_goes16(day: int, hour: int, year: int = 2026) -> dict:
    downloaded = {}
    hr = f"{hour:02d}"; dy = f"{day:03d}"
    bands = {"C07": "M6C07", "C13": "M6C13", "C14": "M6C14"}
    for bname, bsuff in bands.items():
        prefix = f"ABI-L2-CMIPF/{year}/{dy}/{hr}/"
        flist = s3_ls(prefix)
        target = None
        for f in flist:
            if bsuff in f and f.endswith(".nc"):
                target = f; break
        if target:
            local = os.path.join(DATA_DIR, f"GOES16_{bname}_{dy}_{hr}.nc")
            print(f"  DL {bname}: {target}")
            ok = s3_download(f"{prefix}{target}", local)
            if ok:
                downloaded[bname] = local
                print(f"    -> {os.path.basename(local)} ({os.path.getsize(local)/1e6:.1f} MB)")
    # FDCF
    prefix = f"ABI-L2-FDCF/{year}/{dy}/{hr}/"
    flist = s3_ls(prefix)
    target = None
    for f in flist:
        if "FDCF" in f and f.endswith(".nc"):
            target = f; break
    if target:
        local = os.path.join(DATA_DIR, f"GOES16_FDCF_{dy}_{hr}.nc")
        print(f"  DL FDCF: {target}")
        ok = s3_download(f"{prefix}{target}", local)
        if ok:
            downloaded["FDCF"] = local
            print(f"    -> {os.path.basename(local)} ({os.path.getsize(local)/1e6:.1f} MB)")
    return downloaded


def detect_hotspots_kmeans_goes16(c07_path, c13_path, c14_path) -> list:
    ds7 = nc.Dataset(c07_path)
    ds13 = nc.Dataset(c13_path)
    ds14 = nc.Dataset(c14_path)

    c07 = apply_scale(ds7, 'CMI')
    c13 = apply_scale(ds13, 'CMI')
    c14 = apply_scale(ds14, 'CMI')

    x_v = ds7.variables['x']
    y_v = ds7.variables['y']
    xx, yy = np.meshgrid(x_v[:], y_v[:])
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(xx, yy, GOES16_LON)
    ts = extract_timestamp(c07_path)

    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )
    if len(idx[0]) == 0:
        for d in [ds7, ds13, ds14]: d.close()
        return []

    print(f"  Pixels CE: {len(idx[0])}")

    pixels = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t7 = float(c07[yi, xi]); t13 = float(c13[yi, xi]); t14 = float(c14[yi, xi])
        btd_7_14 = t7 - t14
        if np.isnan(t7) or np.isnan(t13): continue
        pixels.append({'yi': yi, 'xi': xi, 'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
                       't07': t7, 't13': t13, 't14': t14, 'btd_7_14': btd_7_14})

    # Threshold candidates
    threshold_candidates = []
    for p in pixels:
        if p['t07'] > 330 and p['btd_7_14'] > 5:
            threshold_candidates.append({**p, 'confidence': 'alta'})
        elif p['t07'] > 320 and p['btd_7_14'] > 3:
            threshold_candidates.append({**p, 'confidence': 'media'})
        elif p['t07'] > 310 and p['btd_7_14'] > 2:
            threshold_candidates.append({**p, 'confidence': 'baixa'})

    # K-Means refinement
    if len(threshold_candidates) >= 3:
        pixel_map, features = {}, []
        for fc in threshold_candidates:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = fc['yi']+dy, fc['xi']+dx
                    if 0 <= ny < c07.shape[0] and 0 <= nx < c07.shape[1]:
                        t7 = float(c07[ny, nx]); t13 = float(c13[ny, nx]); t14 = float(c14[ny, nx])
                        btd = t7 - t14
                        if not (np.isnan(t7) or np.isnan(t13)) and (ny, nx) not in pixel_map:
                            pixel_map[(ny, nx)] = {'lat': float(lat_arr[ny, nx]), 'lon': float(lon_arr[ny, nx]),
                                                   't07': t7, 't13': t13, 't14': t14, 'btd_7_14': btd}
                            features.append([t7, t13, btd])
        if len(features) >= 5:
            f = np.array(features); f_norm = (f - f.mean(axis=0)) / (f.std(axis=0) + 1e-10)
            kmeans = KMeans(n_clusters=min(2, len(f_norm)), random_state=42, n_init='auto')
            labels = kmeans.fit_predict(f_norm)
            # Find fire cluster (higher T07 mean)
            c0_t07 = f[labels==0, 0].mean() if np.any(labels==0) else 0
            c1_t07 = f[labels==1, 0].mean() if np.any(labels==1) else 0
            fire_label = 0 if c0_t07 > c1_t07 else 1
            keys = list(pixel_map.keys())
            kmeans_px = [pixel_map[keys[i]] for i, lbl in enumerate(labels) if lbl == fire_label]
            for p in kmeans_px:
                if p['t07'] > 315 and p['btd_7_14'] > 2:
                    p['confidence'] = 'kmeans'; p['source'] = 'CMIPF_KMeans'; p['timestamp'] = ts
                    threshold_candidates.append(p)

    # Deduplicate
    final = []
    for d in threshold_candidates:
        is_dup = False
        for ex in final:
            ld = abs(d['lat'] - ex['lat'])*111000
            lnd = abs(d['lon'] - ex['lon'])*111000*abs(math.cos(math.radians(d['lat'])))
            if math.sqrt(ld**2 + lnd**2) < 2000:
                is_dup = True; break
        if not is_dup:
            final.append(d)
    for d in [ds7, ds13, ds14]: d.close()
    return final


def detect_fire_from_fdcf_goes16(fdcf_path: str) -> list:
    """
    FDCF DQF: 0=good fire pixel, 1=fire-free land, 2=cloud, 3=other invalid, 4-5=error
    """
    ds = nc.Dataset(fdcf_path)
    dqf = ds.variables['DQF'][:]
    temp = apply_scale(ds, 'Temp')
    power = apply_scale(ds, 'Power')
    area = apply_scale(ds, 'Area')

    x_v, y_v = ds.variables['x'], ds.variables['y']
    xx, yy = np.meshgrid(x_v[:], y_v[:])
    lat_arr, lon_arr = goes_fixed_grid_to_latlon(xx, yy, GOES16_LON)
    ts = extract_timestamp(fdcf_path)

    dqf_filled = dqf.filled(255) if hasattr(dqf, 'filled') else dqf
    fire_mask = dqf_filled == 0  # Good quality fire pixel

    # Ceará filter
    ce_idx = np.where(fire_mask &
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX))

    results = []
    for i in range(len(ce_idx[0])):
        yi, xi = ce_idx[0][i], ce_idx[1][i]
        t_k = float(temp[yi, xi]) * getattr(ds.variables['Temp'], 'scale_factor', 1.0) + getattr(ds.variables['Temp'], 'add_offset', 0.0)
        results.append({
            'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
            'temperature_k': t_k,
            'frp_mw': float(power[yi, xi]),
            'area_m2': float(area[yi, xi]),
            'source': 'FDCF', 'timestamp': ts,
        })
    ds.close()
    return results


def run():
    print("=" * 60)
    print("GOES-16 Pipeline de Detecção de Queimadas — Ceará")
    print("=" * 60)
    now = datetime.now(timezone.utc)
    print(f"UTC: {now.strftime('%Y-%m-%d %H:%M')}, DOY={now.timetuple().tm_yday}")

    candidates = []
    for off in [0, -1, -2, -3, -4, -5]:
        t = now + timedelta(hours=off)
        candidates.append((t.timetuple().tm_yday, t.hour))
    # Also check yesterday daytime
    yesterday = now - timedelta(days=1)
    for h in range(12, 24):
        candidates.append((yesterday.timetuple().tm_yday, h))
    candidates = list(set(candidates))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    all_fire, all_fdcf = [], []
    success = False

    for day, hour in candidates[:15]:
        print(f"\nTrying day={day}, hour={hour:02d}...")
        prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
        files = s3_ls(prefix)
        if not files or not any("C07" in f for f in files):
            print(f"  No C07 data")
            continue
        print(f"  Found CMIPF data")
        dl = download_goes16(day, hour)
        if "C07" in dl and "C13" in dl and "C14" in dl:
            success = True
            print(f"\n--- CMIPF/K-Means ---")
            px = detect_hotspots_kmeans_goes16(dl["C07"], dl["C13"], dl["C14"])
            print(f"  Detections: {len(px)}")
            all_fire.extend(px)
            if "FDCF" in dl:
                print(f"\n--- FDCF ---")
                fdcf_px = detect_fire_from_fdcf_goes16(dl["FDCF"])
                print(f"  FDCF: {len(fdcf_px)}")
                all_fdcf.extend(fdcf_px)
            break

    if not success:
        print("\nNo GOES-16 data available. Checking fallback days...")
        for day in [now.timetuple().tm_yday - 1, now.timetuple().tm_yday - 2]:
            for hour in range(12, 23):
                prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
                files = s3_ls(prefix)
                if files and any("C07" in f for f in files):
                    dl = download_goes16(day, hour)
                    if "C07" in dl and "C13" in dl and "C14" in dl:
                        px = detect_hotspots_kmeans_goes16(dl["C07"], dl["C13"], dl["C14"])
                        print(f"  CMIPF: {len(px)}")
                        all_fire.extend(px)
                        if "FDCF" in dl:
                            fdcf_px = detect_fire_from_fdcf_goes16(dl["FDCF"])
                            print(f"  FDCF: {len(fdcf_px)}")
                            all_fdcf.extend(fdcf_px)
                    break
            if all_fire:
                break

    print(f"\n{'='*60}\nRESULTS\n{'='*60}")
    print(f"CMIPF+KMeans: {len(all_fire)} | FDCF: {len(all_fdcf)}")
    if all_fire:
        for fp in all_fire:
            print(f"  lat={fp['lat']:.4f} lon={fp['lon']:.4f} T07={fp['t07']:.1f}K BTD={fp['btd_7_14']:.1f}K")
    if all_fdcf:
        for fp in all_fdcf:
            print(f"  FDCF: lat={fp['lat']:.4f} lon={fp['lon']:.4f} T={fp['temperature_k']:.1f}K FRP={fp['frp_mw']:.1f}MW")

    results = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "satellite": "GOES-16 (75.2W)",
        "cmipf_kmeans": all_fire,
        "fdcf": all_fdcf,
        "total_cmipf": len(all_fire),
        "total_fdcf": len(all_fdcf),
        "total_combined": len(all_fire) + len(all_fdcf),
    }
    out_path = os.path.join(DATA_DIR, "goes16_detection_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")
    print(f"\nCross-validation:")
    print(f"  INPE: 11 focos (CSV 2 dias)")
    print(f"  GOES-16 CMIPF: {len(all_fire)}")
    print(f"  GOES-16 FDCF: {len(all_fdcf)}")
    return results


if __name__ == "__main__":
    run()
