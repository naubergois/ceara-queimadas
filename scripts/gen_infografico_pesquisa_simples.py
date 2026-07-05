#!/usr/bin/env python3
"""Generate simple research infographic (Portuguese) via xAI Grok Imagine."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "infografico_pesquisa_simples.png"

PROMPT = """
Infográfico educativo em PORTUGUÊS (Brasil), formato vertical para celular (9:16).
Título grande no topo: "Gêmeo Digital de Queimadas — Ceará"

Seções com ícones simples e texto GRANDE legível (sem parágrafos pequenos):

1) O PROBLEMA
"Queimadas no Ceará exigem resposta rápida. Dados de satélite chegam em várias fontes e são difíceis de interpretar."

2) A SOLUÇÃO
Três passos com setas:
"Satélites (INPE · NASA · GOES-16) + clima"
→ "IA agentica (LangGraph) cruza e valida"
→ "Alertas explicáveis para defesa civil"

3) COMO FUNCIONA
Três badges coloridos:
VERDE "NÃO — sem risco"
AMARELO "INCERTO — monitorar"
VERMERO "SIM — alerta imediato"

4) RESULTADOS (2025)
"84% precisão · 92% recall"
"184 dias · estação seca · dados INPE"

5) PARA QUEM
"Defesa civil · gestores ambientais · pesquisadores"

Rodapé:
"Código aberto MIT · github.com/naubergois/ceara-queimadas · Demo: 98.91.177.145"

Estilo: infográfico flat moderno, fundo branco, azul marinho e laranja, mapa estilizado do Ceará, SEM texto minúsculo, SEM watermark, SEM foto realista. Texto 100% em português.
""".strip()


def main() -> None:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        sys.exit("XAI_API_KEY not set")

    payload = {
        "model": "grok-imagine-image-quality",
        "prompt": PROMPT,
        "n": 1,
        "aspect_ratio": "9:16",
        "resolution": "2k",
    }
    req = urllib.request.Request(
        "https://api.x.ai/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    print("Gerando infográfico Grok...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())

    item = data["data"][0]
    if item.get("url"):
        img_req = urllib.request.Request(
            item["url"],
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(img_req, timeout=120) as img_resp:
            raw = img_resp.read()
    elif item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    else:
        sys.exit(f"No image in response: {data}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(raw)
    print(f"Salvo {OUT} ({len(raw)} bytes)")


if __name__ == "__main__":
    main()
