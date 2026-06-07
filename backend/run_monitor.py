#!/usr/bin/env python3
"""Cron monitor: run FIRMS + INPE + GOES-16 collection and print results."""
import sys
sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

from app.services.firms_real import coletar_focos_firms_real
from app.services.inpe_service import coletar_focos_inpe
from app.services.goes16_service import coletar_dados_goes16


async def run():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = {
        "timestamp": ts,
        "firms": {"count": 0, "severidade": {}, "recentes": []},
        "inpe": {"count": 0, "recentes": []},
        "goes16": {"count": 0, "recentes": []},
        "total": 0,
    }

    # --- FIRMS ---
    try:
        firms = await coletar_focos_firms_real(dias=1)
        report["firms"]["count"] = len(firms)
        if firms:
            sev = Counter(f["severidade"] for f in firms)
            report["firms"]["severidade"] = dict(sev)
            for f in sorted(firms, key=lambda x: x["data_hora"], reverse=True)[:5]:
                report["firms"]["recentes"].append({
                    "data_hora": f["data_hora"][:16],
                    "lat": round(f["lat"], 4),
                    "lon": round(f["lon"], 4),
                    "severidade": f["severidade"],
                    "frp": f["frp"],
                    "satelite": f.get("satelite", ""),
                })
    except Exception as e:
        report["firms"]["error"] = str(e)

    # --- INPE ---
    try:
        inpe = await coletar_focos_inpe(estado="CE")
        report["inpe"]["count"] = len(inpe)
        if inpe:
            for f in inpe[:5]:
                dt = f.data_hora.strftime("%Y-%m-%d %H:%M") if f.data_hora else "N/A"
                report["inpe"]["recentes"].append({
                    "data_hora": dt,
                    "lat": round(f.latitude, 4),
                    "lon": round(f.longitude, 4),
                    "satelite": f.satelite,
                    "municipio": f.municipio,
                    "bioma": f.bioma,
                })
    except Exception as e:
        report["inpe"]["error"] = str(e)

    # --- GOES-16 ---
    try:
        goes = await coletar_dados_goes16(horas_atras=6)
        report["goes16"]["count"] = len(goes)
        if goes:
            for g in goes[:3]:
                report["goes16"]["recentes"].append({
                    "data_hora": str(g.data_hora),
                    "lat": round(g.latitude, 4),
                    "lon": round(g.longitude, 4),
                    "temp_k": g.temperatura_pixel_k,
                    "frp_mw": g.frp_mw,
                })
    except Exception as e:
        report["goes16"]["error"] = str(e)

    report["total"] = report["firms"]["count"] + report["inpe"]["count"] + report["goes16"]["count"]
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    asyncio.run(run())
