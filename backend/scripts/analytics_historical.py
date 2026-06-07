#!/usr/bin/env python3
"""
Cross-validation: Run GOES-19 K-Means on day 155 historical data (when INPE fires were active)
This gives us a proper temporal overlap for metrics computation.
"""
import os, sys, json, math
from datetime import datetime, timezone

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA = f"{BASE}/data"
sys.path.insert(0, f"{BASE}/scripts")

# Import the GOES-19 pipeline functions
sys.path.insert(0, f"{BASE}/scripts")
from goes19_pipeline import download_goes19, detect_hotspots_kmeans, detect_fire_from_fdcf

# INPE reference fires with timestamps
inpe_fires = [
    {"lat": -4.36166, "lon": -37.90058, "sat": "NOAA-20", "dt": "2026-06-04 03:19", "frp": 3.0},
    {"lat": -4.36657, "lon": -37.89973, "sat": "NOAA-21", "dt": "2026-06-04 04:08", "frp": 2.5},
    {"lat": -4.36299, "lon": -37.89918, "sat": "NOAA-21", "dt": "2026-06-04 04:08", "frp": 2.3},
    {"lat": -4.36295, "lon": -37.90092, "sat": "NPP-375D", "dt": "2026-06-04 04:42", "frp": 2.4},
    {"lat": -4.36547, "lon": -37.90318, "sat": "NPP-375", "dt": "2026-06-04 15:39", "frp": 4.6},
    {"lat": -4.36473, "lon": -37.89816, "sat": "NPP-375", "dt": "2026-06-04 15:39", "frp": 4.6},
    {"lat": -4.36388, "lon": -37.90091, "sat": "NOAA-20", "dt": "2026-06-04 15:58", "frp": 8.9},
    {"lat": -6.62892, "lon": -38.72660, "sat": "NOAA-21", "dt": "2026-06-04 04:08", "frp": 0.7},
    {"lat": -6.58605, "lon": -39.64408, "sat": "NOAA-21", "dt": "2026-06-04 16:43", "frp": 3.2},
    {"lat": -6.61077, "lon": -39.07165, "sat": "NOAA-21", "dt": "2026-06-04 16:43", "frp": 11.3},
    {"lat": -5.05812, "lon": -39.93523, "sat": "NPP-375D", "dt": "2026-06-05 04:21", "frp": 1.7},
]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Process day 155 historical data at hours 15, 16, 17, 18 (closest to INPE fire times)
# These already exist as downloaded files, so download_goes19 will skip
all_fire, all_fdcf = [], []
for hour in [15, 16, 17, 18]:
    print(f"\n{'='*60}")
    print(f"Processing day 155, hour {hour:02d}")
    print('='*60)
    
    # Use existing local files directly instead of re-downloading
    c07_path = f"{DATA}/GOES19_C07_155_{hour:02d}.nc"
    c13_path = f"{DATA}/GOES19_C13_155_{hour:02d}.nc"
    c14_path = f"{DATA}/GOES19_C14_155_{hour:02d}.nc"
    fdcf_path = f"{DATA}/GOES19_FDCF_155_{hour:02d}.nc"
    
    if os.path.exists(c07_path) and os.path.exists(c13_path) and os.path.exists(c14_path):
        print(f"  Using cached files for hour {hour:02d}")
        try:
            px = detect_hotspots_kmeans(c07_path, c13_path, c14_path)
            print(f"  CMIPF detections: {len(px)}")
            all_fire.extend(px)
        except Exception as e:
            print(f"  Error CMIPF: {e}")
        
        if os.path.exists(fdcf_path):
            try:
                fdcf_px = detect_fire_from_fdcf(fdcf_path)
                print(f"  FDCF detections: {len(fdcf_px)}")
                all_fdcf.extend(fdcf_px)
            except Exception as e:
                print(f"  Error FDCF: {e}")
    else:
        print(f"  Files not cached, skipping hour {hour:02d}")

print(f"\n{'='*60}")
print(f"TOTAL HISTÓRICO (dia 155): CMIPF={len(all_fire)} | FDCF={len(all_fdcf)}")
print('='*60)

# Deduplicate (same logic as pipeline)
final = []
for d in all_fire:
    is_dup = False
    for ex in final:
        ld = abs(d['lat'] - ex['lat'])*111000
        lnd = abs(d['lon'] - ex['lon'])*111000*abs(math.cos(math.radians(d['lat'])))
        if math.sqrt(ld**2 + lnd**2) < 2000:
            is_dup = True; break
    if not is_dup:
        final.append(d)

print(f"  After dedup: {len(final)} detections")

# Match vs INPE (2km radius)
tp = 0
matched = set()
for d in final:
    for i, ref in enumerate(inpe_fires):
        if i in matched: continue
        dist = haversine(d["lat"], d["lon"], ref["lat"], ref["lon"])
        if dist < 2000:
            tp += 1
            matched.add(i)
            print(f"  MATCH! GOES-19 ({d['lat']:.4f},{d['lon']:.4f}, T07={d['t07']:.1f}K) "
                  f"<-> INPE ({ref['lat']:.4f},{ref['lon']:.4f}, {ref['sat']}) "
                  f"dist={dist:.0f}m")

fp = len(final) - tp
fn = len(inpe_fires) - len(matched)
prec = tp/(tp+fp) if (tp+fp) > 0 else 0
rec = tp/(tp+fn) if (tp+fn) > 0 else 0
f1 = 2*prec*rec/(prec+rec) if (prec+rec) > 0 else 0

print(f"\n📊 MÉTRICAS (GOES-19 dia 155 vs INPE)")
print(f"  TP: {tp}  FP: {fp}  FN: {fn}")
print(f"  Precisão: {prec:.4f}")
print(f"  Revocação: {rec:.4f}")
print(f"  F1-Score: {f1:.4f}")

# Also check proximity within 10km (more lenient for GOES 2km resolution)
print(f"\n   Proximidade (10km radius, compensa resolução 2km do ABI):")
tp10 = 0
matched10 = set()
for d in final:
    for i, ref in enumerate(inpe_fires):
        if i in matched10: continue
        dist = haversine(d["lat"], d["lon"], ref["lat"], ref["lon"])
        if dist < 10000:
            tp10 += 1
            matched10.add(i)
            break

fp10 = len(final) - tp10
fn10 = len(inpe_fires) - len(matched10)
prec10 = tp10/(tp10+fp10) if (tp10+fp10) > 0 else 0
rec10 = tp10/(tp10+fn10) if (tp10+fn10) > 0 else 0
f110 = 2*prec10*rec10/(prec10+rec10) if (prec10+rec10) > 0 else 0

print(f"  TP: {tp10}  FP: {fp10}  FN: {fn10}")
print(f"  Precisão: {prec10:.4f}")
print(f"  Revocação: {rec10:.4f}")
print(f"  F1-Score: {f110:.4f}")

# Temperature analysis
if final:
    temps = [p["t07"] for p in final]
    print(f"\n   Estatísticas térmicas (dia 155):")
    print(f"     T07 médio: {sum(temps)/len(temps):.1f}K")
    print(f"     T07 max: {max(temps):.1f}K")
    print(f"     T07 min: {min(temps):.1f}K")
