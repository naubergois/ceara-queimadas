#!/usr/bin/env python3
"""Debug: list GOES file availability by DOY/hour."""
import os, re
DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

def extract_ts(fname):
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", fname)
    if m:
        return int(m.group(2)), int(m.group(3))
    return 0, 0

files_by_key = {}
for fname in sorted(os.listdir(DATA_DIR)):
    if not fname.endswith(".nc") or "OR_ABI" not in fname:
        continue
    doy, hr = extract_ts(fname)
    band = "unknown"
    if "M6C07" in fname: band = "C07"
    elif "M6C13" in fname: band = "C13"
    elif "M6C14" in fname: band = "C14"
    key = (doy, hr)
    if key not in files_by_key: files_by_key[key] = {}
    files_by_key[key][band] = fname

for (doy, hr) in sorted(files_by_key.keys()):
    bands = files_by_key[(doy, hr)]
    c07 = "C07" in bands
    c13 = "C13" in bands
    c14 = "C14" in bands
    status = "OK" if (c07 and c13 and c14) else "MISS"
    print(f"DOY={doy} HR={hr:02d}: {status}  C07={c07} C13={c13} C14={c14}")
