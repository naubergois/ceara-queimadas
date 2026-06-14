#!/usr/bin/env python3
"""Check available DOYs with both C07 and C13 data."""
import os, re

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
files = os.listdir(DATA_DIR)

c07_doys = set()
c13_doys = set()
for fname in files:
    if fname.endswith('.nc') and '163' not in fname:
        m = re.search(r'_s2026(\d{3})', fname)
        if m:
            if 'M6C07' in fname:
                c07_doys.add(int(m.group(1)))
            if 'M6C13' in fname:
                c13_doys.add(int(m.group(1)))

print('C07 DOYs:', sorted(c07_doys))
print('C13 DOYs:', sorted(c13_doys))
both = sorted(c07_doys & c13_doys)
print('Both:', both)

# Also check hours per DOY for common data (for GOES19 simplified format)
for doy in both:
    hours_c07 = set()
    hours_c13 = set()
    for fname in files:
        if fname.endswith('.nc') and f'_s2026{doy:03d}' in fname:
            hrs = re.search(r'_s2026\d{3}(\d{2})', fname)
            if hrs:
                if 'M6C07' in fname:
                    hours_c07.add(int(hrs.group(1)))
                if 'M6C13' in fname:
                    hours_c13.add(int(hrs.group(1)))
    common = sorted(hours_c07 & hours_c13)
    print(f'  DOY {doy}: C07={sorted(hours_c07)} C13={sorted(hours_c13)} common={common}')
