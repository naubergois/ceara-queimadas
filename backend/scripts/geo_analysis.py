#!/usr/bin/env python3
"""TASK-105: Análise geoespacial focos FIRMS/INPE no Ceará"""
import os, sys, json, math
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")
BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
ARTIFACTS_DIR = "/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

import asyncio

print("=" * 70)
print("TASK-105: Análise Geoespacial — Focos FIRMS/INPE vs GOES")
print("=" * 70)
print(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

# Load FIRMS data
print("\n[1] Carregando FIRMS...")
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
firms = []
try:
    from app.services.firms_real import coletar_focos_firms_real
    firms = loop.run_until_complete(coletar_focos_firms_real(dias=3))
    print(f"  FIRMS: {len(firms)} focos")
except Exception as e:
    print(f"  FIRMS error: {e}")

# Load INPE data
print("\n[2] Carregando INPE...")
inpe = []
try:
    from app.services.inpe_service import coletar_focos_inpe
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=3)
    focos = loop.run_until_complete(coletar_focos_inpe(data_inicio=inicio, data_fim=agora, estado="CE"))
    for f in focos:
        inpe.append({
            "lat": f.latitude,
            "lon": f.longitude,
            "frp": getattr(f, 'frp', 0) or 0,
            "satelite": getattr(f, 'satelite', '') or '',
            "data_hora": f.data_hora.strftime('%Y-%m-%d %H:%M:%S UTC') if hasattr(f, 'data_hora') and f.data_hora else '',
            "bioma": getattr(f, 'bioma', '') or '',
            "municipio": getattr(f, 'municipio', '') or '',
        })
    print(f"  INPE: {len(inpe)} focos")
except Exception as e:
    print(f"  INPE error: {e}")

loop.close()

# Geo-spatial analysis
print("\n[3] Análise geoespacial...")

# Bounding box statistics
lats = [f['lat'] for f in firms] + [f['lat'] for f in inpe]
lons = [f['lon'] for f in firms] + [f['lon'] for f in inpe]

print(f"  Extensão: lat=[{min(lats):.4f}, {max(lats):.4f}] lon=[{min(lons):.4f}, {max(lons):.4f}]")

# Cluster analysis — count by 1-degree bins
from collections import Counter
lat_bins = [int(lat) for lat in lats]
lon_bins = [int(lon) for lon in lons]
lat_counter = Counter(lat_bins)
lon_counter = Counter(lon_bins)

print(f"  Regiões mais ativas (por grau de latitude):")
for lat, count in sorted(lat_counter.most_common(5)):
    print(f"    Lat {lat}°: {count} focos")

print(f"  Regiões mais ativas (por grau de longitude):")
for lon, count in sorted(lon_counter.most_common(5)):
    print(f"    Lon {lon}°: {count} focos")

# Time distribution of FIRMS fires
print(f"\n[4] Distribuição temporal FIRMS (quando os satélites polares passam):")
firms_dates = {}
for f in firms:
    dt_str = f.get('data_hora', '')
    if dt_str:
        day = dt_str[:10]
        firms_dates[day] = firms_dates.get(day, 0) + 1

for day, count in sorted(firms_dates.items()):
    print(f"  {day}: {count} focos")

# FRP distribution
frp_vals = [f.get('frp', 0) or 0 for f in firms]
frp_vals_inpe = [f.get('frp', 0) or 0 for f in inpe]
all_frp = frp_vals + frp_vals_inpe
if all_frp:
    print(f"\n  FRP: min={min(all_frp):.1f} max={max(all_frp):.1f} mean={sum(all_frp)/len(all_frp):.1f} median={sorted(all_frp)[len(all_frp)//2]:.1f}")

# Satellite distribution
sat_ct = Counter(f.get('satelite', 'N/A') for f in inpe)
print(f"\n  Distribuição por satélite (INPE):")
for sat, count in sat_ct.most_common():
    print(f"    {sat}: {count}")

# Check if any fires fall within GOES Ceará grid hours
print(f"\n[5] Análise de cobertura temporal GOES × FIRMS:")
print(f"  GOES-19 cobre Ceará 08z-22z (DOY 157) e 08z-17z (DOY 158)")
print(f"  FIRMS = VIIRS (passagens polares ~1:30 e 13:30 local)")
print(f"  INPE = MODIS + VIIRS + GOES (fontes diversas)")
print(f"  Diferença fundamental: GOES é geoestacionário (instantâneo)," )
print(f"  VIIRS é polar (cobre CE 2x/dia) — orçamento amostral diferente")

# Combined deduped reference
all_ref = []
for f in firms:
    all_ref.append({'lat': f['lat'], 'lon': f['lon'], 'source': 'FIRMS', 'frp': f.get('frp', 0)})
for f in inpe:
    all_ref.append({'lat': f['lat'], 'lon': f['lon'], 'source': 'INPE', 'frp': f.get('frp', 0)})

deduped = []
for r in all_ref:
    is_dup = False
    for e in deduped:
        ld = abs(r['lat'] - e['lat']) * 111000
        lnd = abs(r['lon'] - e['lon']) * 111000 * abs(math.cos(math.radians(r['lat'])))
        if math.sqrt(ld**2 + lnd**2) < 500:
            is_dup = True
            break
    if not is_dup:
        deduped.append(r)

print(f"\n  Focos únicos combinados: {len(deduped)}")
print(f"    FIRMS: {len(firms)}  INPE: {len(inpe)}  Deduped: {len(deduped)}")

# Save geo analysis
geo_report = {
    "firms_count": len(firms),
    "inpe_count": len(inpe),
    "combined_deduped": len(deduped),
    "bbox": {"lat_min": min(lats), "lat_max": max(lats), "lon_min": min(lons), "lon_max": max(lons)},
    "firms_by_day": firms_dates,
    "satellite_distribution": dict(sat_ct),
    "season_note": "Inverno CE (junho) - estação chuvosa, baixa atividade de queimadas",
    "goes_coverage_note": "GOES-19 cobre 08z-22z, mas Tmax C07=298K < threshold 310K",
    "recommendation": "Reexecutar validação em ago-out (estação seca) para F1 quantitativo"
}

json_path = os.path.join(ARTIFACTS_DIR, "TASK-105-geo-analysis.json")
with open(json_path, "w") as f:
    json.dump(geo_report, f, indent=2, default=str)
print(f"\n  JSON: {json_path}")

print("\nTASK-105: Análise geoespacial CONCLUÍDA")
