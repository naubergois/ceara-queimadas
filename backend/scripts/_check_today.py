#!/usr/bin/env python3
"""Check what GOES data is available today (June 6, 2026)."""
import os, subprocess, json
from datetime import datetime, timezone

today = datetime.now(timezone.utc)
doy = today.timetuple().tm_yday
print(f"Today: {today.strftime('%Y-%m-%d')} DOY={doy}")

# Check S3 for GOES-19 data available today
# GOES-19 = noaa-goes19 bucket
# Path: ABI-L2-CMIPF/<year>/<doy>/<hour>/
BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
# List all NC files sorted by mtime
all_nc = sorted([f for f in os.listdir(BASE) if f.endswith('.nc') and 'test' not in f])
print(f"\nAll NC files ({len(all_nc)}):")
for f in all_nc:
    mtime = os.path.getmtime(os.path.join(BASE, f))
    mt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    print(f"  {f} (mtime: {mt.strftime('%m-%d %H:%M')})")
