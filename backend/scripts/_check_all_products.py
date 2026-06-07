#!/usr/bin/env python3
"""Check what GOES products are available today."""
import subprocess, xml.etree.ElementTree as ET

BUCKET = "noaa-goes19"
DAY = "157"

# List top-level prefixes for today
url = f"https://{BUCKET}.s3.amazonaws.com/?prefix=ABI-L2-/2026/{DAY}/12/&max-keys=100"
result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=15)

if result.returncode == 0 and "<Contents>" in result.stdout:
    root = ET.fromstring(result.stdout)
    ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
    nc_files = [k for k in keys if k.endswith('.nc')]
    
    # Group by product type and band
    products = {}
    for k in nc_files:
        parts = k.split('/')
        # Product is at index 0 (ABI-L2-CMIPF)
        prod = parts[0]
        fname = parts[-1]
        if prod not in products:
            products[prod] = set()
        # Extract band info
        if 'M6C' in fname:
            band = fname.split('M6C')[1][:2]
            products[prod].add(f"Band {band}")
        elif 'M6' in fname:
            products[prod].add("Multi-band")
        else:
            products[prod].add("Unknown")
    
    for prod, bands in sorted(products.items()):
        print(f"{prod}: {sorted(bands)}")
else:
    print("No data found")
    
# Also check the ABI-L2-CMIP product (different from CMIPF)
for prefix in ["ABI-L2-CMIP/2026/157/00/", "ABI-L2-CMIPF/2026/157/"]:
    url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={prefix}&max-keys=5"
    result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        keys_in = [k for k in result.stdout.split('\n') if 'Key' in k]
        print(f"\n{prefix}: {len([k for k in result.stdout.split() if '.nc' in k])} .nc files")
