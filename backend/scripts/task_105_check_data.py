#!/usr/bin/env python3
"""Check available data for TASK-105 validation."""
import json, os, sys, re
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")
DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"

print("=" * 60)
print("TASK-105: CHECK AVAILABLE DATA")
print("=" * 60)

# 1. GOES-19 data available
print("\n[GOES-19 FILES]")
goes_files = [f for f in os.listdir(DATA_DIR) if f.startswith("GOES19") and f.endswith(".nc")]
print(f"  Total: {len(goes_files)}")

c07_files = sorted([f for f in goes_files if "C07" in f])
c13_files = sorted([f for f in goes_files if "C13" in f])
c14_files = sorted([f for f in goes_files if "C14" in f])

print(f"  C07 (SWIR ~3.9um): {len(c07_files)}")
print(f"  C13 (Clean LWIR): {len(c13_files)}")
print(f"  C14 (CO2 LWIR):   {len(c14_files)}")

# Spot recent files
print("\n  Recent C07 files (last 5):")
for f in c07_files[-5:]:
    path = os.path.join(DATA_DIR, f)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    print(f"    {f} ({size_mb:.1f} MB, modified {mtime.strftime('%Y-%m-%d %H:%M')})")

# 2. INPE Historical data
print("\n[INPE HISTORICAL DATA]")
hist_path = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/experiments/data/inpe_ceara_historico.json"
if os.path.exists(hist_path):
    with open(hist_path) as f:
        inpe_data = json.load(f)
    dates = set(d.get('date', '') for d in inpe_data)
    print(f"  Total records: {len(inpe_data)}")
    print(f"  Date range: {min(dates)} to {max(dates)}")
    biomes = {}
    for d in inpe_data:
        b = d.get('bioma', 'N/A').strip()
        biomes[b] = biomes.get(b, 0) + 1
    print(f"  Biomes: {biomes}")
    satelites = {}
    for d in inpe_data:
        s = d.get('satelite', 'N/A').strip()
        satelites[s] = satelites.get(s, 0) + 1
    print(f"  Satellites: {satelites}")
    frps = [float(d.get('frp', 0)) for d in inpe_data if d.get('frp', '').strip()]
    if frps:
        print(f"  FRP: min={min(frps):.1f} max={max(frps):.1f} mean={sum(frps)/len(frps):.1f}")
else:
    print("  File not found!")

# 3. Previous artifacts
print("\n[PREVIOUS ARTIFACTS]")
if os.path.exists(ARTIFACTS_DIR):
    artifacts = os.listdir(ARTIFACTS_DIR)
    for a in sorted(artifacts):
        fpath = os.path.join(ARTIFACTS_DIR, a)
        fsize = os.path.getsize(fpath)
        print(f"  {a} ({fsize} bytes)")
else:
    print(f"  Creating artifacts dir: {ARTIFACTS_DIR}")
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

print("\nDone.")
