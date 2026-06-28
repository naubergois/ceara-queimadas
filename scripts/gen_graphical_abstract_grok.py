#!/usr/bin/env python3
"""Generate EMS graphical abstract via xAI Grok Imagine API."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "graphical_abstract.png"
OUT_HD = ROOT / "submission" / "graphical_abstract_2k.png"

PROMPT = """
Professional Elsevier journal GRAPHICAL ABSTRACT — wide landscape banner (13:5 aspect ratio).
Topic: Open-source wildfire monitoring Digital Twin for Ceará, Brazil.

Layout left-to-right in 4 large panels with BOLD READABLE English labels (minimum 24pt equivalent, high contrast):

PANEL 1 — "Satellite data": icons NASA FIRMS, GOES-16, INPE focos, Open-Meteo weather.

PANEL 2 — "LangGraph pipeline (10 nodes)": simple flowchart with nodes: ingest → validate → analyze → fuse → classify → alert.

PANEL 3 — "Three-class alerts": three colored badges NO (green), UNCERTAIN (yellow), YES (red) with arrow to civil defense.

PANEL 4 — "Results": large text "84% precision · 92% recall" and subtitle "2025 dry season · 184 days INPE".

Footer center: "Ceará Wildfire Platform · MIT open source · github.com/naubergois/ceara-queimadas"

Style: clean flat scientific infographic, white background, navy blue and orange accent colors, NO tiny text, NO paragraph text, NO watermark, NO photorealistic clutter. All text must be sharp and legible at thumbnail size. Similar quality to academic software architecture diagrams.
""".strip()


def main() -> None:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        sys.exit("XAI_API_KEY not set")

    payload = {
        "model": "grok-imagine-image-quality",
        "prompt": PROMPT,
        "n": 1,
        "aspect_ratio": "16:9",
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
    print("Calling Grok Imagine (grok-imagine-image-quality)...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())

    item = data["data"][0]
    if item.get("url"):
        img_req = urllib.request.Request(
            item["url"],
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(img_req, timeout=120) as img_resp:
            raw = img_resp.read()
    elif item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    else:
        sys.exit(f"No image in response: {data}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_HD.write_bytes(raw)
    print(f"Saved {OUT_HD} ({len(raw)} bytes)")

    try:
        from PIL import Image

        img = Image.open(OUT_HD)
        # EMS minimum: 1328 x 531 (w x h) — upscale if needed, then crop/resize to exact banner
        target_w, target_h = 1328, 531
        ratio = target_w / target_h
        w, h = img.size
        current = w / h
        if current > ratio:
            new_h = h
            new_w = int(h * ratio)
        else:
            new_w = w
            new_h = int(w / ratio)
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        img = img.crop((left, top, left + new_w, top + new_h))
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        img.save(OUT, format="PNG", optimize=True)
        print(f"EMS crop → {OUT} ({target_w}x{target_h})")
    except ImportError:
        OUT.write_bytes(raw)
        print(f"PIL missing — copied full image to {OUT}")


if __name__ == "__main__":
    main()
