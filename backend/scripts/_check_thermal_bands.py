#!/usr/bin/env python3
"""Check for Band 7 and Band 13 files for today."""
import subprocess, xml.etree.ElementTree as ET, re

BUCKET = "noaa-goes19"
DAY = "157"

# Check for Band 07 (3.9µm - SWIR) and Band 13 (10.3µm - TIR1) 
print(f"Checking GOES-19 DOY{DAY} for CMIP Band 07 and Band 13 files...")
print()

for hour in range(6, 19):  # 06:00 to 18:00 UTC (daylight hours)
    for band in ["07", "13"]:
        prefix = f"ABI-L2-CMIPF/2026/{DAY}/{hour:02d}/"  
        url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=10"
        result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "<Contents>" in result.stdout:
            root = ET.fromstring(result.stdout)
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
            band_files = [k for k in keys if k.endswith('.nc') and f'M6C{band}' in k]
            if band_files:
                print(f"  Hour {hour:02d}:00 Band {band}: {len(band_files)} files")
                for bf in band_files[:3]:
                    fname = bf.split('/')[-1]
                    m = re.search(r'_s(\d{14})', fname)
                    scan_ts = m.group(1) if m else '?'
                    print(f"    {scan_ts}")
