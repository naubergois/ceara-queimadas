#!/usr/bin/env python3
"""
Coletor de dados de queimadas — Ceará (Gêmeos Digitais)
Coleta focos do NASA FIRMS, INPE BDQueimadas e GOES-16.
Uso: python3 coletor.py [--dias N]
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")

from app.services.firms_real import coletar_focos_firms_real
from app.services.inpe_service import coletar_focos_inpe
from app.services.goes16_service import coletar_dados_goes16

BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_RED = "\033[91m"
BRIGHT_CYAN = "\033[96m"
RESET = "\033[0m"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=1, help="Janela em dias para FIRMS (default: 1)")
    args = parser.parse_args()

    print(f"{BRIGHT_CYAN}=== Coletor de Dados — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ==={RESET}")

    # --- NASA FIRMS ---
    print(f"\n{BRIGHT_YELLOW}--- NASA FIRMS ---{RESET}")
    firms = []
    try:
        firms = await coletar_focos_firms_real(dias=args.dias)
        if firms:
            print(f"  {BRIGHT_GREEN}{len(firms)} focos encontrados no Ceará{RESET}")
            by_severity = {}
            for f in firms:
                s = f["severidade"]
                by_severity[s] = by_severity.get(s, 0) + 1
            for sev, count in sorted(by_severity.items()):
                print(f"    Severidade {sev}: {count}")
            # Top 5 mais recentes
            firms_sorted = sorted(firms, key=lambda x: x["data_hora"], reverse=True)[:5]
            print(f"  Top 5 mais recentes:")
            for f in firms_sorted:
                print(f"    [{f['data_hora'][:16]}] lat={f['lat']:.4f} lon={f['lon']:.4f} {f['severidade']} conf={f['confianca']}")
        else:
            print(f"  {BRIGHT_YELLOW}Nenhum foco encontrado no período{RESET}")
    except Exception as e:
        print(f"  {BRIGHT_RED}ERRO: {e}{RESET}")

    # --- INPE ---
    print(f"\n{BRIGHT_YELLOW}--- INPE BDQueimadas ---{RESET}")
    inpe = []
    try:
        inpe = await coletar_focos_inpe(estado="CE")
        if inpe:
            print(f"  {BRIGHT_GREEN}{len(inpe)} focos encontrados no Ceará{RESET}")
            for f in inpe[:5]:
                dt = f.data_hora.strftime("%Y-%m-%d %H:%M") if f.data_hora else "N/A"
                print(f"    [{dt}] lat={f.latitude:.4f} lon={f.longitude:.4f} sat={f.satelite} munic={f.municipio}")
        else:
            print(f"  {BRIGHT_YELLOW}Nenhum foco encontrado{RESET}")
    except Exception as e:
        print(f"  {BRIGHT_RED}ERRO: {e}{RESET}")

    # --- GOES-16 ---
    print(f"\n{BRIGHT_YELLOW}--- GOES-16 (ABI-L2-FDCF) ---{RESET}")
    goes16 = []
    try:
        goes16 = await coletar_dados_goes16(horas_atras=6)
        if goes16:
            print(f"  {BRIGHT_GREEN}{len(goes16)} pixels de fogo detectados{RESET}")
            for g in goes16[:5]:
                print(f"    [{g.data_hora}] lat={g.latitude:.4f} lon={g.longitude:.4f} temp={g.temperatura_pixel_k}K")
        else:
            print(f"  {BRIGHT_YELLOW}Nenhum pixel de fogo detectado nas últimas 6h{RESET}")
    except Exception as e:
        print(f"  {BRIGHT_RED}ERRO: {e}{RESET}")

    total_firms = len(firms) if firms else 0
    total_inpe = len(inpe) if inpe else 0
    total_goes = len(goes16) if goes16 else 0
    print(f"\n{BRIGHT_CYAN}=== Coleta concluída ({datetime.now(timezone.utc).strftime('%H:%M UTC')}) ==={RESET}")
    print(f"  FIRMS={total_firms}  INPE={total_inpe}  GOES-16={total_goes}")
    sys.exit(0 if total_firms + total_inpe + total_goes > 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
