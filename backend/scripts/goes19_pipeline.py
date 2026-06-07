#!/usr/bin/env python3
"""
GOES-19 Pipeline de Detecção de Queimadas — Ceará
Usa pyproj para conversão correta de coordenadas.
GOES-19 está em 75.2°W — cobre o Ceará (lat: -7.85 a -2.78, lon: -41.42 a -37.25).
"""
import os, sys, json, math, re, subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
import netCDF4 as nc
from sklearn.cluster import KMeans
from pyproj import Proj

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

S3_BUCKET = "noaa-goes19"
SAT_LON = -75.0  # GOES-19 longitude
H = 35786023.0   # Satellite height (m)
R_EQ = 6378137.0
R_POL = 6356752.3142

CEARA_LAT_MIN, CEARA_LAT_MAX = -7.85, -2.78
CEARA_LON_MIN, CEARA_LON_MAX = -41.42, -37.25

# Pre-create pyproj GEOS projection
GEOS_PROJ = Proj(proj='geos', lon_0=SAT_LON, h=H, a=R_EQ, b=R_POL)


def fixed_grid_to_latlon(x_rad, y_rad):
    """
    Convert GOES fixed grid (x,y in radians) to lat/lon using pyproj.
    For GOES-R ABI (sweep=x convention):
      X = H * tan(x_scan)
      Y = H * tan(y_scan) / cos(x_scan)  (sweep=x)
    """
    # Handle numpy arrays
    x = np.asarray(x_rad, dtype=np.float64)
    y = np.asarray(y_rad, dtype=np.float64)
    
    # Convert to projection coordinates (meters)
    X = H * np.tan(x)
    Y = H * np.tan(y) / np.cos(x)  # sweep=x convention
    
    lon, lat = GEOS_PROJ(X, Y, inverse=True)
    return np.asarray(lat), np.asarray(lon)


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


def download_goes19(day: int, hour: int, year: int = 2026) -> dict:
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
            local = os.path.join(DATA_DIR, f"GOES19_{bname}_{dy}_{hr}.nc")
            print(f"  DL {bname}: {target[:50]}...")
            ok = s3_download(f"{prefix}{target}", local)
            if ok:
                downloaded[bname] = local
                print(f"    -> {os.path.basename(local)} ({os.path.getsize(local)/1e6:.1f} MB)")
    prefix = f"ABI-L2-FDCF/{year}/{dy}/{hr}/"
    flist = s3_ls(prefix)
    target = None
    for f in flist:
        if "FDCF" in f and f.endswith(".nc"):
            target = f; break
    if target:
        local = os.path.join(DATA_DIR, f"GOES19_FDCF_{dy}_{hr}.nc")
        print(f"  DL FDCF: {target[:50]}...")
        ok = s3_download(f"{prefix}{target}", local)
        if ok:
            downloaded["FDCF"] = local
            print(f"    -> {os.path.basename(local)} ({os.path.getsize(local)/1e6:.1f} MB)")
    return downloaded


def detect_hotspots_kmeans(c07_path, c13_path, c14_path) -> list:
    ds7 = nc.Dataset(c07_path)
    ds13 = nc.Dataset(c13_path)
    ds14 = nc.Dataset(c14_path)

    c07 = np.array(ds7.variables['CMI'][:], dtype=np.float64)  # Already in BT (K)
    c13 = np.array(ds13.variables['CMI'][:], dtype=np.float64)  # Already in BT (K)
    c14 = np.array(ds14.variables['CMI'][:], dtype=np.float64)  # Already in BT (K)

    x_v = ds7.variables['x'][:]
    y_v = ds7.variables['y'][:]
    xx, yy = np.meshgrid(x_v, y_v)
    lat_arr, lon_arr = fixed_grid_to_latlon(xx, yy)
    ts = extract_timestamp(c07_path)

    idx = np.where(
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX)
    )
    if len(idx[0]) == 0:
        for d in [ds7, ds13, ds14]: d.close()
        return []

    print(f"  Pixels in Ceará: {len(idx[0])}")
    pixels = []
    for i in range(len(idx[0])):
        yi, xi = idx[0][i], idx[1][i]
        t7 = float(c07[yi, xi]); t13 = float(c13[yi, xi]); t14 = float(c14[yi, xi])
        btd = t7 - t14
        if np.isnan(t7) or np.isnan(t13): continue
        pixels.append({'yi': yi, 'xi': xi, 'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
                       't07': t7, 't13': t13, 't14': t14, 'btd_7_14': btd})

    threshold = []
    for p in pixels:
        if p['t07'] > 330 and p['btd_7_14'] > 5:
            threshold.append({**p, 'confidence': 'alta'})
        elif p['t07'] > 320 and p['btd_7_14'] > 3:
            threshold.append({**p, 'confidence': 'media'})
        elif p['t07'] > 310 and p['btd_7_14'] > 2:
            threshold.append({**p, 'confidence': 'baixa'})

    if len(threshold) >= 3:
        pixel_map, features = {}, []
        for fc in threshold:
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
            f = np.array(features)
            f_norm = (f - f.mean(axis=0)) / (f.std(axis=0) + 1e-10)
            kmeans = KMeans(n_clusters=min(2, len(f_norm)), random_state=42, n_init='auto')
            labels = kmeans.fit_predict(f_norm)
            c0 = f[labels==0, 0].mean() if np.any(labels==0) else 0
            c1 = f[labels==1, 0].mean() if np.any(labels==1) else 0
            fire_label = 0 if c0 > c1 else 1
            keys = list(pixel_map.keys())
            for i, lbl in enumerate(labels):
                if lbl == fire_label:
                    p = pixel_map[keys[i]]
                    if p['t07'] > 315 and p['btd_7_14'] > 2:
                        p['confidence'] = 'kmeans'
                        p['source'] = 'CMIPF_KMeans'
                        p['timestamp'] = ts
                        threshold.append(p)

    final = []
    for d in threshold:
        is_dup = False
        for ex in final:
            ld = abs(d['lat'] - ex['lat']) * 111000
            lnd = abs(d['lon'] - ex['lon']) * 111000 * abs(math.cos(math.radians(d['lat'])))
            if math.sqrt(ld**2 + lnd**2) < 2000:
                is_dup = True; break
        if not is_dup:
            final.append(d)
    for d in [ds7, ds13, ds14]: d.close()
    return final


def detect_fire_from_fdcf(fdcf_path: str) -> list:
    ds = nc.Dataset(fdcf_path)
    dqf = np.array(ds.variables['DQF'][:], dtype=np.int32)
    temp = np.array(ds.variables['Temp'][:], dtype=np.float64)  # Already in K
    power = np.array(ds.variables['Power'][:], dtype=np.float64)
    area = np.array(ds.variables['Area'][:], dtype=np.float64)

    x_v = ds.variables['x'][:]
    y_v = ds.variables['y'][:]
    xx, yy = np.meshgrid(x_v, y_v)
    lat_arr, lon_arr = fixed_grid_to_latlon(xx, yy)
    ts = extract_timestamp(fdcf_path)

    dqf_filled = dqf  # Already a regular array, not masked
    fire_mask = dqf_filled == 0

    ce_idx = np.where(fire_mask &
        (lat_arr >= CEARA_LAT_MIN) & (lat_arr <= CEARA_LAT_MAX) &
        (lon_arr >= CEARA_LON_MIN) & (lon_arr <= CEARA_LON_MAX))

    results = []
    for i in range(len(ce_idx[0])):
        yi, xi = ce_idx[0][i], ce_idx[1][i]
        t_k = temp[yi, xi]
        results.append({
            'lat': float(lat_arr[yi, xi]), 'lon': float(lon_arr[yi, xi]),
            'temperature_k': float(t_k),
            'frp_mw': float(power[yi, xi]),
            'area_m2': float(area[yi, xi]),
            'source': 'FDCF', 'timestamp': ts,
        })
    ds.close()
    return results


def run():
    print("=" * 60)
    print("GOES-19 Pipeline (pyproj correção) — Ceará")
    print("=" * 60)
    now = datetime.now(timezone.utc)
    print(f"UTC: {now.strftime('%Y-%m-%d %H:%M')}, DOY={now.timetuple().tm_yday}")

    candidates = []
    for off in [0, -1, -2, -3]:
        t = now + timedelta(hours=off)
        candidates.append((t.timetuple().tm_yday, t.hour))
    yesterday = now - timedelta(days=1)
    for h in range(8, 24):
        candidates.append((yesterday.timetuple().tm_yday, h))
    candidates = list(set(candidates))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    all_fire, all_fdcf = [], []
    success = False

    for day, hour in candidates[:20]:
        print(f"\nTrying day={day}, hour={hour:02d}...")
        prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
        files = s3_ls(prefix)
        if not files or not any("C07" in f for f in files):
            print(f"  No C07 data")
            continue
        print(f"  Found CMIPF data")
        dl = download_goes19(day, hour)
        if "C07" in dl and "C13" in dl and "C14" in dl:
            success = True
            print(f"\n--- CMIPF/K-Means ---")
            px = detect_hotspots_kmeans(dl["C07"], dl["C13"], dl["C14"])
            print(f"  Detections: {len(px)}")
            all_fire.extend(px)
            if "FDCF" in dl:
                print(f"\n--- FDCF ---")
                fdcf_px = detect_fire_from_fdcf(dl["FDCF"])
                print(f"  FDCF: {len(fdcf_px)}")
                all_fdcf.extend(fdcf_px)
            break

    if not success:
        print("\nNo recent data. Trying fallback days...")
        for day in [now.timetuple().tm_yday - 1, now.timetuple().tm_yday - 2]:
            for hour in range(8, 23):
                prefix = f"ABI-L2-CMIPF/2026/{day:03d}/{hour:02d}/"
                files = s3_ls(prefix)
                if files and any("C07" in f for f in files):
                    dl = download_goes19(day, hour)
                    if "C07" in dl and "C13" in dl and "C14" in dl:
                        px = detect_hotspots_kmeans(dl["C07"], dl["C13"], dl["C14"])
                        all_fire.extend(px)
                        if "FDCF" in dl:
                            fdcf_px = detect_fire_from_fdcf(dl["FDCF"])
                            all_fdcf.extend(fdcf_px)
                    break
            if all_fire: break

    print(f"\n{'='*60}\nRESULTS\n{'='*60}")
    print(f"CMIPF+KMeans: {len(all_fire)} | FDCF: {len(all_fdcf)}")
    if all_fire:
        for fp in all_fire:
            print(f"  CMIPF: lat={fp['lat']:.4f} lon={fp['lon']:.4f} T07={fp['t07']:.1f}K BTD={fp['btd_7_14']:.1f}K conf={fp.get('confidence','N/A')}")
    if all_fdcf:
        for fp in all_fdcf:
            print(f"  FDCF: lat={fp['lat']:.4f} lon={fp['lon']:.4f} T={fp['temperature_k']:.1f}K FRP={fp['frp_mw']:.1f}MW")

    # Also try day 155 for cross-validation
    if not all_fire and not all_fdcf:
        print(f"\n--- Trying day 155 (yesterday, INPE reported 10+ fires) ---")
        for hour in [4, 15, 16, 17, 18]:
            prefix = f"ABI-L2-CMIPF/2026/155/{hour:02d}/"
            files = s3_ls(prefix)
            if files and any("C07" in f for f in files):
                print(f"\nDay 155 hour {hour:02d}...")
                dl = download_goes19(155, hour)
                if "C07" in dl and "C13" in dl and "C14" in dl:
                    px = detect_hotspots_kmeans(dl["C07"], dl["C13"], dl["C14"])
                    all_fire.extend(px)
                    if "FDCF" in dl:
                        fdcf_px = detect_fire_from_fdcf(dl["FDCF"])
                        all_fdcf.extend(fdcf_px)
                        print(f"  FDCF: {len(fdcf_px)}")

    results = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "satellite": "GOES-19 (75W) com pyproj",
        "cmipf_kmeans": all_fire,
        "fdcf": all_fdcf,
        "total_cmipf": len(all_fire),
        "total_fdcf": len(all_fdcf),
        "total_combined": len(all_fire) + len(all_fdcf),
    }
    out_path = os.path.join(DATA_DIR, "goes19_detection_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")
    print(f"\nCross-validation:")
    print(f"  INPE CSV (2 days): 11 focos")
    print(f"  GOES-19 CMIPF: {len(all_fire)}")
    print(f"  GOES-19 FDCF: {len(all_fdcf)}")
    return results


if __name__ == "__main__":
    run()
