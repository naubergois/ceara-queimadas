#!/usr/bin/env python3
"""
Coletor direto de focos de queimada INPE BDQueimadas para Ceará.
Usa CSVs públicos do dataserver-coids.inpe.br.
"""
import csv
import io
import json
import sys
from datetime import datetime, timezone

import requests

UF = "CE"
ARGS_DIAS = int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 2

BASE = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil"
agora = datetime.now(timezone.utc)

focos = []

for i in range(ARGS_DIAS):
    data = agora - timedelta(days=i) if i > 0 else agora
    from datetime import timedelta
    data = agora - timedelta(days=i)
    data_str = data.strftime("%Y%m%d")
    url = f"{BASE}/focos_diario_br_{data_str}.csv"
    print(f"[{data_str}] Baixando {url}...", file=sys.stderr)

    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"  ERRO HTTP {resp.status_code}", file=sys.stderr)
        continue

    # Decodifica explicitamente como UTF-8 (o CSV é UTF-8)
    content = resp.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    count = 0
    for row in reader:
        estado = (row.get("estado") or "").strip().upper()
        # CEARÁ (UTF-8) ou CEARÁ (latin-1) ou CE
        estado_clean = estado.replace("Á", "A").replace("Ã", "A").replace("\x81", "A")
        if estado not in (UF, "CEARÁ") and estado_clean != "CEARA":
            continue

        focos.append({
            "id": row.get("id", "").strip(),
            "lat": (row.get("lat") or "").strip(),
            "lon": (row.get("lon") or "").strip(),
            "data_hora_gmt": (row.get("data_hora_gmt") or "").strip(),
            "satelite": (row.get("satelite") or "").strip(),
            "municipio": (row.get("municipio") or "").strip(),
            "estado": estado,
            "bioma": (row.get("bioma") or "").strip(),
            "risco_fogo": (row.get("risco_fogo") or "").strip(),
            "frp": (row.get("frp") or "").strip(),
        })
        count += 1

    print(f"  => {count} focos CE", file=sys.stderr)

# --- Saída formatada ---
print()
print("=" * 100)
print(f"RELATÓRIO DE FOCOS DE QUEIMADA — CEARÁ (UF 23)")
print(f"Fonte: INPE BDQueimadas (dataserver-coids.inpe.br) — CSVs diários")
print(f"Período: últimas {ARGS_DIAS} dia(s) (até {agora.strftime('%Y-%m-%d %H:%M UTC')})")
print(f"Total de focos no Ceará: {len(focos)}")
print("=" * 100)

if focos:
    # Por bioma
    biomas = {}
    for f in focos:
        b = f["bioma"] or "N/I"
        biomas[b] = biomas.get(b, 0) + 1
    print("\n📊 Focos por Bioma:")
    print(f"  {'Bioma':25s} {'Focos':>6s}")
    print(f"  {'─'*25} {'─'*6}")
    for b, q in sorted(biomas.items(), key=lambda x: -x[1]):
        print(f"  {b:25s} {q:6d}")

    # Por município
    municipios = {}
    for f in focos:
        m = f["municipio"] or "N/I"
        if m not in municipios:
            municipios[m] = {"focos": 0, "biomas": set(), "satelites": set()}
        municipios[m]["focos"] += 1
        if f["bioma"]:
            municipios[m]["biomas"].add(f["bioma"])
        if f["satelite"]:
            municipios[m]["satelites"].add(f["satelite"])

    print("\n📊 Focos por Município:")
    print(f"  {'Município':30s} {'Focos':>6s} {'Bioma(s)':20s} {'Satélite(s)':20s}")
    print(f"  {'─'*30} {'─'*6} {'─'*20} {'─'*20}")
    for m, info in sorted(municipios.items(), key=lambda x: -x[1]["focos"]):
        biomas_str = ", ".join(sorted(info["biomas"]))[:20] or "N/I"
        sat_str = ", ".join(sorted(info["satelites"]))[:20] or "N/I"
        print(f"  {m:30s} {info['focos']:6d} {biomas_str:20s} {sat_str:20s}")

    # Tabela detalhada
    print("\n📋 Tabela completa de focos:")
    print(f"  {'Data/Hora GMT':22s} {'Satélite':12s} {'Latitude':>10s} {'Longitude':>10s} {'Município':25s} {'Bioma':15s} {'R.Fogo':>6s} {'FRP':>8s}")
    print(f"  {'─'*22} {'─'*12} {'─'*10} {'─'*10} {'─'*25} {'─'*15} {'─'*6} {'─'*8}")
    for f in sorted(focos, key=lambda x: x["data_hora_gmt"]):
        print(f"  {f['data_hora_gmt']:22s} {f['satelite']:12s} {f['lat']:>10s} {f['lon']:>10s} {f['municipio']:25s} {f['bioma']:15s} {f['risco_fogo']:>6s} {f['frp']:>8s}")

    # Satélites
    satelites = {}
    for f in focos:
        s = f["satelite"] or "N/I"
        satelites[s] = satelites.get(s, 0) + 1
    print("\n📊 Focos por Satélite:")
    for s, q in sorted(satelites.items(), key=lambda x: -x[1]):
        print(f"  {s:12s}: {q} focos")

print()
print("=" * 100)
print(f"Fonte: INPE / BDQueimadas — {BASE}")
print(f"Dados refletem apenas os satélites de referência do INPE.")
print("=" * 100)
