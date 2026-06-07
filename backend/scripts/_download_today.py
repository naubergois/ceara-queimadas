#!/usr/bin/env python3
"""Download GOES-19 Band 07 and Band 13 from S3 for today (DOY157)."""
import subprocess, os, re
from datetime import datetime

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
os.makedirs(BASE, exist_ok=True)

BUCKET = "noaa-goes19"
DAY = "157"
HOURS = ["08", "09", "10", "11", "12"]

def s3_list(prefix):
    """List S3 objects with pagination."""
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=500"
    result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return []
    keys = []
    for line in result.stdout.split('<Key>'):
        if '.nc' in line and '</Key>' in line:
            k = line.split('</Key>')[0]
            if k.strip():
                keys.append(k.strip())
    return keys

def download_if_newer(s3_key, local_path):
    """Download file if not exists locally."""
    if os.path.exists(local_path):
        return False
    url = f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
    print(f"  Downloading: {s3_key.split('/')[-1]}")
    result = subprocess.run(['curl', '-s', '-o', local_path, url], capture_output=True, text=True, timeout=120)
    if result.returncode == 0 and os.path.exists(local_path):
        sz = os.path.getsize(local_path)
        print(f"    -> {sz//1024//1024}MB")
        return True
    else:
        print(f"    FAILED: {result.stderr[:100] if result.stderr else 'Unknown error'}")
        return False

print(f"Downloading GOES-19 DOY{DAY} Band 07 and Band 13 data...")
print(f"Time: {datetime.now().strftime('%H:%M:%S')}")

total_new = 0
for hour in HOURS:
    prefix = f"ABI-L2-CMIPF/2026/{DAY}/{hour}/"
    keys = s3_list(prefix)
    
    for key in keys:
        # Match C07 or C13 files
        if 'M6C07' in key or 'M6C13' in key:
            fname = key.split('/')[-1]
            local_path = os.path.join(BASE, fname)
            if download_if_newer(key, local_path):
                total_new += 1

print(f"\nTotal nuevos: {total_new}")
if total_new > 0:
    print("Lista de arquivos:")
    for f in sorted(os.listdir(BASE)):
        if f.endswith('.nc') and ('M6C07' in f or 'M6C13' in f) and '2026157' in f:
            print(f"  {f}")
