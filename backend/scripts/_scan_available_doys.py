#!/usr/bin/env python3
"""Quick scan of available GOES-19 C07+C13 pairs in the data directory."""
import os, re
from datetime import datetime, timedelta, timezone

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

def extract_ts(fname):
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(
            days=int(doy)-1, hours=int(hr), minutes=int(mi), seconds=int(sc)
        )
        return int(doy), int(hr), dt
    return None, None, None

# Old naming: GOES19_C07_155_04.nc
def extract_ts_old(fname):
    m = re.search(r"GOES1\d_C0[713]_(\d{3})_(\d{2})\.nc", fname)
    if m:
        return int(m.group(1)), int(m.group(2)), None
    return None, None, None

pairs = {}
for fname in os.listdir(DATA_DIR):
    if not fname.endswith(".nc"):
        continue
    doy, hr, dt = extract_ts(fname)
    if doy is None:
        doy, hr, dt = extract_ts_old(fname)
    if doy is None:
        continue
    
    is_c07 = "C07" in fname
    is_c13 = "C13" in fname
    is_goes19 = "G19" in fname or "GOES19" in fname
    
    if is_goes19:
        key = (doy, hr)
        if key not in pairs:
            pairs[key] = {"doy": doy, "hr": hr, "c07": False, "c13": False, "dt": dt}
        if is_c07:
            pairs[key]["c07"] = True
        if is_c13:
            pairs[key]["c13"] = True

print("GOES-19 available C07+C13 pairs by DOY:")
print("=" * 60)

by_doy = {}
for key, p in sorted(pairs.items()):
    if p["c07"] and p["c13"]:
        d = p["doy"]
        if d not in by_doy:
            by_doy[d] = []
        by_doy[d].append(p["hr"])

for doy in sorted(by_doy.keys(), reverse=True):
    hours = sorted(by_doy[doy])
    # Compute date
    try:
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=doy-1)
        date_str = dt.strftime("%d/%b")
    except:
        date_str = "?"
    print(f"  DOY {doy} ({date_str}): {len(hours)} hours — {hours}")

# Also scan for GOES-16 (old)
g16_pairs = {}
for fname in os.listdir(DATA_DIR):
    if not fname.endswith(".nc") or "G16" not in fname:
        continue
    m = re.search(r"G16.*_s(\d{4})(\d{3})(\d{2})(\d{2})", fname)
    if not m:
        continue
    doy = int(m.group(2))
    hr = int(m.group(3))
    is_c07 = "C07" in fname
    is_c13 = "C13" in fname
    key = (doy, hr)
    if key not in g16_pairs:
        g16_pairs[key] = {"c07": False, "c13": False}
    if is_c07:
        g16_pairs[key]["c07"] = True
    if is_c13:
        g16_pairs[key]["c13"] = True

g16_by_doy = {}
for key, p in g16_pairs.items():
    if p["c07"] and p["c13"]:
        d = key[0]
        if d not in g16_by_doy:
            g16_by_doy[d] = []
        g16_by_doy[d].append(key[1])

if g16_by_doy:
    print("\nGOES-16 available C07+C13 pairs:")
    for doy in sorted(g16_by_doy.keys(), reverse=True):
        hours = sorted(g16_by_doy[doy])
        print(f"  DOY {doy}: {hours}")

# What is today?
now = datetime.now(timezone.utc)
today_doy = now.timetuple().tm_yday
print(f"\nToday: DOY {today_doy} ({now.strftime('%d/%b/%Y %H:%M UTC')})")
print(f"DOYs available: {sorted(by_doy.keys(), reverse=True)}")

# Check what new data was added since last run
print(f"\nTotal GOES-19 pairs: {len(pairs)} files, {len(by_doy)} DOYs with pairs")
