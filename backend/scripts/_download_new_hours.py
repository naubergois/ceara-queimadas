#!/usr/bin/env python3
"""Download newest C07 and C13 files from S3 for DOY 158, hours 13-18Z"""
import subprocess, os, re

BUCKET = "noaa-goes19"
DAY = "158"
BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
os.makedirs(BASE, exist_ok=True)

def parse_xml(fpath):
    with open(fpath) as f:
        content = f.read()
    keys = re.findall(r'<Key>(.*?)</Key>', content)
    return keys

new_files = []
for hour in range(13, 19):
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix=ABI-L2-CMIPF/2026/{DAY}/{hour:02d}/&max-keys=200"
    xml_path = f"/tmp/s3_hour{hour}.xml"
    subprocess.run(['curl', '-s', '-o', xml_path, url], capture_output=True, timeout=30)
    keys = parse_xml(xml_path)
    
    for key in keys:
        if 'M6C07' in key or 'M6C13' in key:
            fname = key.split('/')[-1]
            local_path = os.path.join(BASE, fname)
            if not os.path.exists(local_path):
                dl_url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
                print(f"Downloading: {fname}")
                r = subprocess.run(['curl', '-s', '-o', local_path, dl_url], capture_output=True, timeout=120)
                if r.returncode == 0 and os.path.exists(local_path):
                    sz = os.path.getsize(local_path)
                    print(f"  -> {sz//1024}KB")
                    new_files.append(fname)
                else:
                    print(f"  FAILED")
    
print(f"\nNew files downloaded: {len(new_files)}")
for f in new_files:
    print(f"  {f}")
