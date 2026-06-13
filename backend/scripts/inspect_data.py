#!/usr/bin/env python3
"""Inspect available GOES data and INPE/FIRMS data for TASK-105."""
import os, sys, re, json
from datetime import datetime, timedelta, timezone

BASE_DIR = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.insert(0, BASE_DIR)

# Scan GOES data
doys = {}
for fname in os.listdir(DATA_DIR):
    if not fname.endswith('.nc'):
        continue
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', fname)
    if not m:
        continue
    yr, dy, hr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if dy not in doys:
        doys[dy] = {'year': yr, 'hours': set(), 'bands': set()}
    doys[dy]['hours'].add(hr)
    if 'C07' in fname: doys[dy]['bands'].add('C07')
    if 'C13' in fname: doys[dy]['bands'].add('C13')
    if 'C14' in fname: doys[dy]['bands'].add('C14')

print("=" * 70)
print("TASK-105: Inspeção de dados disponíveis")
print("=" * 70)
print(f"\nTimestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"\nTotal arquivos NC: {sum(1 for f in os.listdir(DATA_DIR) if f.endswith('.nc'))}")

print("\n--- Dados GOES disponíveis ---")
for d in sorted(doys.keys()):
    info = doys[d]
    hrs = sorted(info['hours'])
    dt = datetime(info['year'], 1, 1, tzinfo=timezone.utc) + timedelta(days=d-1)
    bands = sorted(info['bands'])
    print(f"  DOY {d} ({dt.strftime('%Y-%m-%d')}): bands={bands} hrs={hrs[0]:02d}z-{hrs[-1]:02d}z ({len(hrs)} scans)")

# Check INPE
print("\n--- INPE BDQueimadas ---")
try:
    from app.services.inpe_service import coletar_focos_inpe
    import asyncio
    async def get_inpe():
        agora = datetime.now(timezone.utc)
        inicio = agora - timedelta(days=3)
        focos = await coletar_focos_inpe(data_inicio=inicio, data_fim=agora, estado="CE")
        print(f"  INPE (72h CE): {len(focos)} focos")
        for f in focos[:5]:
            print(f"    lat={f.latitude:.4f} lon={f.longitude:.4f} sat={f.satelite}")
        return focos
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    focos = loop.run_until_complete(get_inpe())
    loop.close()
except Exception as e:
    print(f"  INPE ERROR: {e}")

# Check FIRMS
print("\n--- FIRMS ---")
try:
    from app.services.firms_real import coletar_focos_firms_real
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    firms = loop.run_until_complete(coletar_focos_firms_real(dias=3))
    loop.close()
    print(f"  FIRMS (72h CE): {len(firms)} focos")
    for f in firms[:5]:
        print(f"    lat={f['lat']:.4f} lon={f['lon']:.4f} frp={f['frp']:.1f} sat={f.get('satelite','N/A')}")
except Exception as e:
    print(f"  FIRMS ERROR: {e}")
