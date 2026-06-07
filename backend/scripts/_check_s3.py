#!/usr/bin/env python3
"""Check S3 for new GOES-19 data today via curl."""
import subprocess, os

BUCKET = "noaa-goes19"
PREFIX = "ABI-L2-CMIPF/2026/157/"
url = f"https://{BUCKET}.s3.amazonaws.com/?prefix={PREFIX}&max-keys=5"

print(f"Checking S3: {url}")

result = subprocess.run(
    ["curl", "-s", url],
    capture_output=True, text=True, timeout=15
)

if result.returncode == 0:
    output = result.stdout
    if "<Contents>" in output:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(output)
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
        print(f"DOY157 available: {len(keys)} files")
        for k in keys[:5]:
            print(f"  {k}")
    else:
        print("DOY157: No data available yet (or XML parsing issue)")
        print(f"Response sample: {output[:300]}")
else:
    print(f"Curl error: {result.stderr}")

# Also check DOY156 for the H22 data timestamps
PREFIX2 = "ABI-L2-CMIPF/2026/156/"
url2 = f"https://{BUCKET}.s3.amazonaws.com/?prefix={PREFIX2}&max-keys=5"
result2 = subprocess.run(
    ["curl", "-s", url2],
    capture_output=True, text=True, timeout=15
)
if result2.returncode == 0:
    if "<Contents>" in result2.stdout:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(result2.stdout)
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        keys = [key.text for key in root.findall('.//s3:Key', ns) if key.text]
        print(f"\nDOY156 latest files: {len(keys)} total, showing last 5:")
        for k in keys[-5:]:
            size = root.findall(f'.//s3:Size[../s3:Key=\"{k}\"]', ns)
            sz = size[0].text if size else '?'
            print(f"  {k} ({int(sz)//1024//1024}MB)" if sz != '?' else f"  {k}")
