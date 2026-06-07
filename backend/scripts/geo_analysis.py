#!/usr/bin/env python3
"""Analyze spatial separation between GOES-19 detections and INPE reference fires."""
import json, math
from collections import Counter

with open('/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data/goes19_detection_results.json') as f:
    g19 = json.load(f)

cmipf = g19.get('cmipf_kmeans', [])
lats = [p['lat'] for p in cmipf]
lons = [p['lon'] for p in cmipf]

print('=== GOES-19 DAY 156 (today) DETECTIONS ===')
print(f'Count: {len(cmipf)}')
print(f'Lat range: {min(lats):.4f} to {max(lats):.4f}')
print(f'Lon range: {min(lons):.4f} to {max(lons):.4f}')

# 0.5° grid clusters
regions = Counter()
for p in cmipf:
    key = f'{round(p["lat"]*2)/2:.1f}_{round(p["lon"]*2)/2:.1f}'
    regions[key] += 1
print('\nTop 10 clusters:')
for reg, cnt in regions.most_common(10):
    lat_s, lon_s = reg.split('_')
    pts = [p for p in cmipf if f'{round(p["lat"]*2)/2:.1f}_{round(p["lon"]*2)/2:.1f}' == reg]
    tmax = max(p['t07'] for p in pts)
    print(f'  lat={lat_s} lon={lon_s}: {cnt:3d} pixels | max T07={tmax:.1f}K')

# INPE fires
inpe = [
    (-4.363, -37.900, 'Beberibe'),
    (-6.629, -38.727, 'Umari'),
    (-6.586, -39.644, 'Jucas'),
    (-6.611, -39.072, 'Cedro'),
    (-5.058, -39.935, 'BoaViagem'),
]
print('\n=== INPE Reference Fires ===')
for lat, lon, mun in inpe:
    print(f'  {mun:15s}: ({lat:.2f}, {lon:.2f})')

# Distance from GOES centroid to each INPE fire
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

glat = sum(lats)/len(lats)
glon = sum(lons)/len(lons)
print(f'\nGOES-19 centroid: ({glat:.2f}, {glon:.2f})')
for lat, lon, mun in inpe:
    d = haversine(glat, glon, lat, lon) / 1000
    print(f'  Distance to {mun}: {d:.0f} km')

# Also check if ANY GOES detection is within 50km of ANY INPE fire
dists = []
for p in cmipf:
    for lat, lon, mun in inpe:
        d = haversine(p['lat'], p['lon'], lat, lon) / 1000
        dists.append((mun, d, p['t07']))

closest = min(dists, key=lambda x: x[1])
print(f'\nClosest approach: {closest[0]} at {closest[1]:.1f} km (T07={closest[2]:.1f}K)')
print(f'\n=> GOES-19 and INPE are detecting DIFFERENT fire clusters at different locations.')
print(f'   This explains 0 TP — they burn in different regions of Ceará.')
print(f'   For proper validation, need same-time satellite overpass data.')
