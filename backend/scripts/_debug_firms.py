#!/usr/bin/env python3
"""Debug: print FIRMS data dates and sample."""
import sys
sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")
import asyncio
from app.services.firms_real import coletar_focos_firms_real

async def main():
    firms = await coletar_focos_firms_real(dias=2)
    print(f"Total FIRMS: {len(firms)}")
    datas = set(f.get('data_hora','')[:10] for f in firms if f.get('data_hora'))
    print(f"Datas: {sorted(datas)}")
    for f in firms[:5]:
        print(f"  {str(f.get('data_hora',''))[:16]} lat={f['lat']:.4f} lon={f['lon']:.4f} FRP={f['frp']:.1f} sev={f.get('severidade','')}")

asyncio.run(main())
