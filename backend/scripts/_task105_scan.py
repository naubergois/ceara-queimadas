#!/usr/bin/env python3
"""TASK-105: Scan available data and prepare for validation."""
import os, sys, re, json, math
from datetime import datetime, timedelta, timezone

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

now = datetime.now(timezone.utc)
print(f"Current UTC: {now.strftime('%Y-%m-%d %H:%M:%S')} DOY={now.timetuple().tm_yday}")

# Scan GOES data
doys = {}
for fname in os.listdir(DATA_DIR):
    if not fname.endswith(".nc"): continue
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi, sc = m.groups()
        dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1, hours=int(hr), minutes=int(mi), seconds=int(sc))
        if doy not in doys:
            doys[doy] = {"date": dt.strftime("%Y-%m-%d"), "hours": set(), "files": [], "bands": set()}
        doys[doy]["hours"].add(int(hr))
        doys[doy]["files"].append(fname)
        if "M6C07" in fname: doys[doy]["bands"].add("C07")
        elif "M6C13" in fname: doys[doy]["bands"].add("C13")
        elif "M6C14" in fname: doys[doy]["bands"].add("C14")
        elif "FDCF" in fname: doys[doy]["bands"].add("FDCF")

print("\nGOES-19 Data Available:")
for doy in sorted(doys.keys(), reverse=True):
    d = doys[doy]
    print(f"  DOY {doy} ({d['date']}): {len(d['files'])} files, bands={d['bands']}, hours={sorted(d['hours'])}")

print(f"\nTotal NC files: {len([f for f in os.listdir(DATA_DIR) if f.endswith('.nc')])}")

# Save scan for later use
scan = {
    "timestamp": now.isoformat(),
    "doys": {str(doy): {"date": doys[doy]["date"], "bands": list(doys[doy]["bands"]), 
                        "hours": sorted(doys[doy]["hours"]), "files": len(doys[doy]["files"])}
             for doy in sorted(doys.keys(), reverse=True)}
}
with open(os.path.join(ARTIFACTS_DIR, "TASK-105-data-scan.json"), "w") as f:
    json.dump(scan, f, indent=2)
print(f"\nScan saved to artifacts/TASK-105-data-scan.json")
