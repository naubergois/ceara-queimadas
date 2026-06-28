#!/usr/bin/env python3
"""Generate real INPE monthly hotspot figure from BDQueimadas CSV (stdlib only)."""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv"
OUT = ROOT / "figures/evolucao-focos-inpe-real.png"


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"Missing {CSV}")

    monthly: dict[tuple[int, int], int] = defaultdict(int)
    with CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        date_col = next(c for c in reader.fieldnames if c and ("data" in c.lower() or "date" in c.lower()))
        for row in reader:
            raw = row.get(date_col, "")
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")[:19])
            except ValueError:
                try:
                    dt = datetime.strptime(str(raw)[:10], "%Y-%m-%d")
                except ValueError:
                    continue
            monthly[(dt.year, dt.month)] += 1

    fig, ax = plt.subplots(figsize=(8, 4))
    for year, color in [(2024, "#2B5F8A"), (2025, "#B15533")]:
        months = sorted(m for y, m in monthly if y == year)
        counts = [monthly[(year, m)] for m in months]
        ax.plot(months, counts, "o-", label=f"INPE {year}", color=color, lw=2)
    ax.set_xlabel("Month")
    ax.set_ylabel("Hotspots (INPE BDQueimadas)")
    ax.set_title("Monthly wildfire hotspots — Ceará (real INPE data)")
    ax.set_xticks(range(1, 13))
    ax.legend()
    ax.grid(alpha=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
