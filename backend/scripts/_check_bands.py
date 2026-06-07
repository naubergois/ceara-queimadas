#!/usr/bin/env python3
"""Check S3 for GOES-19 CMIP (multi-band) files or specific band files."""
import subprocess, xml.etree.ElementTree as ET, re

BUCKET = "noaa-goes19"
DAY = "157"
HOUR = "12"  # Latest hour available

# Check what products are available: CMIPF (full resolution) vs CMIPC (conus)
for product in ["ABI-L2-CMIPF", "ABI-L2-FDCF"]:
    prefix = f"{product}/2026/{DAY}/{HOUR}/"
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=50"
    result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=10)
    if result.returncode == 0 and "<Contents>" in result.stdout:
        root = ET.fromstring(result.stdout)
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
        nc_files = [k for k in keys if k.endswith('.nc')]
        print(f"{product}/2026/{DAY}/{HOUR}: {len(nc_files)} files")
        for k in nc_files[:10]:
            # Extract band info
            m = re.search(r'M6C(\d{2})', k)
            band = m.group(1) if m else '?'
            file_size = k.split('/')[-1]
            print(f"  Band {band}: {k.split('/')[-1]}")
