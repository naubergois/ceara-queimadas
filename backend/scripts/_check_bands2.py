#!/usr/bin/env python3
"""Check available bands in GOES-19 DOY156."""
import subprocess, re

url = 'https://noaa-goes19.s3.amazonaws.com/?prefix=ABI-L2-CMIPF/2026/156/00/&max-keys=400'
result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, timeout=15)
if result.returncode == 0:
    bands = set()
    for line in result.stdout.split('<Key>'):
        if 'M6C' in line:
            m = re.search(r'M6C(\d{2})', line)
            if m: bands.add(m.group(1))
    print(f'DOY156 hour 00 bands: {sorted(bands)}')
else:
    print(f'Error: {result.stderr}')
