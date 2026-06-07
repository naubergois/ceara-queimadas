#!/usr/bin/env python3
"""Check S3 for all available GOES-19 hours today."""
import subprocess, xml.etree.ElementTree as ET
from collections import defaultdict

BUCKET = "noaa-goes19"
hours = list(range(0, 24))

for hour in hours:
    prefix = f"ABI-L2-CMIPF/2026/157/{hour:02d}/"
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=5"
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0 and "<Contents>" in result.stdout:
        root = ET.fromstring(result.stdout)
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
        # Count unique files
        nc_files = [k for k in keys if k.endswith('.nc')]
        if nc_files:
            # Get unique scan times (sYYYYDDDHHMMSS)
            scan_times = set()
            for k in nc_files:
                import re
                m = re.search(r'_s(\d{11})', k)
                if m:
                    scan_times.add(m.group(1))
            print(f"GOES-19 DOY157 Hour {hour:02d}:00 - {len(nc_files)} .nc files, {len(scan_times)} scan times")
            for st in sorted(scan_times):
                print(f"  scan: {st}")

print(f"\nAlso checking GOES-16 (noaa-goes16) as backup:")
for hour in [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
    prefix = f"ABI-L2-CMIPF/2026/157/{hour:02d}/"
    url = f"https://noaa-goes16.s3.amazonaws.com/?prefix={prefix}&max-keys=3"
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0 and "<Contents>" in result.stdout:
        root = ET.fromstring(result.stdout)
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
        nc_files = [k for k in keys if k.endswith('.nc')]
        if nc_files:
            print(f"GOES-16 Hour {hour:02d}:00 - {len(nc_files)} files")
