#!/usr/bin/env python3
"""Check GOES-19 band availability for all hours today with pagination."""
import subprocess, re

BUCKET = "noaa-goes19"
DAY = "157"

for hour in [8, 9, 10, 11, 12]:  # Key daylight hours
    prefix = f"ABI-L2-CMIPF/2026/{DAY}/{hour:02d}/"
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=500"
    result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, timeout=15)
    if result.returncode == 0 and '<Contents>' in result.stdout:
        bands = set()
        for line in result.stdout.split('<Key>'):
            if 'M6C' in line and '.nc' in line:
                m = re.search(r'M6C(\d{2})', line)
                if m: bands.add(m.group(1))
        has_07 = '07' in bands
        has_13 = '13' in bands
        print(f"Hour {hour:02d}: {len(bands)} bands | C07={'✓' if has_07 else '✗'} C13={'✓' if has_13 else '✗'} C14={'✓' if '14' in bands else '✗'} bands={sorted(bands)}")
    else:
        print(f"Hour {hour:02d}: No data")
