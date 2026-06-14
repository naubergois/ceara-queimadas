#!/usr/bin/env python3
"""Check DOY 163-165 data availability."""
import os, re

DATA_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
files = os.listdir(DATA_DIR)

for doy in [163, 164, 165]:
    c07_files = []
    c13_files = []
    for fname in files:
        if fname.endswith('.nc') and f's2026{doy:03d}' in fname:
            if 'M6C07' in fname:
                c07_files.append(fname)
            if 'M6C13' in fname:
                c13_files.append(fname)
    if c07_files or c13_files:
        print(f'DOY {doy}: C07={len(c07_files)} files, C13={len(c13_files)} files')
        if c07_files:
            hrs = sorted([int(re.search(r'_s2026\d{3}(\d{2})', f).group(1)) for f in c07_files if re.search(r'_s2026\d{3}(\d{2})', f)])
            print(f'  C07 hours: {hrs}')
        if c13_files:
            hrs = sorted([int(re.search(r'_s2026\d{3}(\d{2})', f).group(1)) for f in c13_files if re.search(r'_s2026\d{3}(\d{2})', f)])
            print(f'  C13 hours: {hrs}')
    else:
        print(f'DOY {doy}: no data')
