#!/usr/bin/env python3
"""Process GOES-19 daytime data from June 5 (DOY156 H15Z) for fire detection."""
import sys, json
sys.path.insert(0, '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/scripts')

# Re-import the cron analysis functions
from cron_analysis import process_goes_data, GOES16_LON, GOES18_LON, report, OUTPUT_DIR
import os
from datetime import datetime

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"

# GOES-19 DOY156 H15Z - daytime scan
c07 = os.path.join(BASE, "GOES19_C07_156_15.nc")
c13 = os.path.join(BASE, "GOES19_C13_156_15.nc")

print("="*80)
print("GOES-19 DOY156 H15Z (15:00 UTC) - Daytime Scan")
print("="*80)

result = process_goes_data(c07, c13, "GOES-19 (day)", GOES18_LON)

if result:
    print(f"\nTimestamp: {result['timestamp']}")
    print(f"Pixels Ceará: {result['pixels_ceara']}")
    print(f"Valid pixels: {result.get('valid_pixels', 0)}")
    print(f"T07 range: {result['stats']['t07_min']}K - {result['stats']['t07_max']}K")
    print(f"T07 mean: {result['stats']['t07_mean']}K")
    print(f"BTD range: {result['stats']['btd_min']}K - {result['stats']['btd_max']}K")
    print(f"≥315K+BTD>2K: {result['hotspots_gte_315k']}")
    print(f"≥320K+BTD>3K: {result['hotspots_gte_320k']}")
    print(f"≥330K+BTD>5K: {result['hotspots_gte_330k']}")
    
    if result.get('kmeans_clusters'):
        print("\nK-Means Clusters:")
        for c in result['kmeans_clusters']:
            mark = "🔥" if c['is_fire'] else "🌲" if c['mean_t07'] < 300 else "⛅"
            print(f"  Cluster {c['cluster']}: {c['pct']}% | T07={c['mean_t07']}K | BTD={c['mean_btd']}K | {mark}")
    
    if result.get('hotspots'):
        print(f"\nTop 20 hotspots:")
        for h in result['hotspots'][:10]:
            print(f"  {h['lat']}, {h['lon']}: T07={h['t07']}K BTD={h['btd']}K")
    
    # Save structured result
    output = {
        "satellite": "GOES-19",
        "timestamp": result['timestamp'],
        "scan": "DOY156_H15Z",
        "pixels_ceara": result['pixels_ceara'],
        "valid_pixels": result.get('valid_pixels', 0),
        "stats": result['stats'],
        "hotspots_gte_315k": result['hotspots_gte_315k'],
        "hotspots_gte_320k": result['hotspots_gte_320k'],
        "hotspots_gte_330k": result['hotspots_gte_330k'],
        "clusters": result.get('kmeans_clusters', []),
        "fire_cluster_mean_t07": result.get('fire_cluster_mean_t07', 0),
    }
    
    json_path = os.path.join(BASE, "goes19_doy156_h15z_analysis.json")
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {json_path}")
else:
    print("Failed to process.")
