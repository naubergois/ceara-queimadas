#!/usr/bin/env python3
"""Process GOES-19 daytime data from June 4 (DOY155)."""
import sys, json
sys.path.insert(0, '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/scripts')

from cron_analysis import process_goes_data, GOES18_LON, report
from cron_analysis import extract_timestamp, apply_scale_and_offset, goes_fixed_grid_to_latlon, extract_goes_projection
from cron_analysis import CEARA_LAT_MIN, CEARA_LAT_MAX, CEARA_LON_MIN, CEARA_LON_MAX
import os
from datetime import datetime
from collections import OrderedDict

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

# GOES-19 DOY155 scans to check
scans = [
    ("GOES19_C07_155_15.nc", "GOES19_C13_155_15.nc", "DOY155 15:00 UT"),
    ("GOES19_C07_155_16.nc", "GOES19_C13_155_16.nc", "DOY155 16:00 UT"),
    ("GOES19_C07_155_17.nc", "GOES19_C13_155_17.nc", "DOY155 17:00 UT"),
    ("GOES19_C07_155_18.nc", "GOES19_C13_155_18.nc", "DOY155 18:00 UT"),
]

for i, (c07, c13, label) in enumerate(scans):
    print(f"\n{'='*60}")
    print(f"GOES-19 {label}")
    print('='*60)
    c07_path = os.path.join(BASE, c07)
    c13_path = os.path.join(BASE, c13)
    result = process_goes_data(c07_path, c13_path, f"GOES-19 {label}", GOES18_LON)
    
    if result and result.get('cobre_ceara', False) and result.get('valid_pixels', 0) > 0:
        print(f"T07: {result['stats']['t07_min']}K - {result['stats']['t07_max']}K (mean={result['stats']['t07_mean']}K)")
        print(f"≥315K+BTD>2K: {result['hotspots_gte_315k']}")
        print(f"≥320K+BTD>3K: {result['hotspots_gte_320k']}")
        print(f"≥330K+BTD>5K: {result['hotspots_gte_330k']}")
        
        if result.get('kmeans_clusters'):
            for c in result['kmeans_clusters']:
                mark = "🔥" if c['is_fire'] else "🌲" if c['mean_t07'] < 300 else "⛅"
                print(f"  Cluster {c['cluster']}: {c['pct']}% | T07={c['mean_t07']}K | BTD={c['mean_btd']}K | {mark}")
        
        if result.get('hotspots'):
            print(f"  Hotspots: {len(result['hotspots'])}")
            for h in result['hotspots'][:5]:
                print(f"    {h['lat']}, {h['lon']}: T07={h['t07']}K BTD={h['btd']}K")
