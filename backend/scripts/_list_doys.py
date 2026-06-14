#!/usr/bin/env python3
"""Scan available GOES data files and group by DOY."""
import os, re
from datetime import datetime, timezone, timedelta

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

doys = {}
for fname in sorted(os.listdir(DATA_DIR)):
    if not fname.endswith(".nc"):
        continue
    if "M6C07" not in fname and "M6C13" not in fname and "M6C14" not in fname:
        continue
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})", fname)
    if m:
        year, doy, hr, mi = m.groups()
        key = f"DOY{doy}"
        if key not in doys:
            doys[key] = {"year": year, "hours": set(), "has_C07": False, "has_C13": False, "has_C14": False, "files": []}
        doys[key]["hours"].add(int(hr))
        if "M6C07" in fname:
            doys[key]["has_C07"] = True
        if "M6C13" in fname:
            doys[key]["has_C13"] = True
        if "M6C14" in fname:
            doys[key]["has_C14"] = True
        doys[key]["files"].append(fname)

# Convert to calendar date
start = datetime(2026, 1, 1, tzinfo=timezone.utc)
for doy_key, info in sorted(doys.items(), key=lambda x: int(x[0][3:])):
    doy_num = int(doy_key[3:])
    dt = start + timedelta(days=doy_num - 1)
    date_str = dt.strftime("%b %d")
    hours_str = ",".join(f"{h:02d}" for h in sorted(info["hours"]))
    bands = []
    if info["has_C07"]: bands.append("C07")
    if info["has_C13"]: bands.append("C13")
    if info["has_C14"]: bands.append("C14")
    print(f"{doy_key} ({date_str}): {len(info['files'])} files, hours=[{hours_str}], bands={'+'.join(bands)}, year={info['year']}")
