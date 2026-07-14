"""
Precision-recall operating-point map for the Exp-B alert iteration (v3-v9).

Plots the published operating points from the manuscript tables (Exp-B
iteration history, three-class YES thresholds, and dry-season 2025
operational validation) in precision-recall space with iso-F1 contours.
All values are taken verbatim from the published result tables; no model
is retrained, so the figure is exactly consistent with the manuscript.

Sources (manuscript tables / result files):
  - tab:task083-evolution  (v3, v5, v6, v7)        <- TASK-083 iteration MDs
  - tab:three_class        (XGB@0.30, XGB@0.50, NeKo YES, v8/v9)
  - tab:alert-levels       (combined YES+UNCERTAIN coverage)
  - tab:extended-temporal  (dry-season 2025 operational point)

Outputs:
  figures/pr-operating-points.png  (repo root, used by the manuscript)

Run:
  cd backend && python -m experiments.pr_curve_figure
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIGURES_DIR = Path(__file__).parent.parent.parent / "figures"

# (label, precision, recall) - binary iteration path, tab:task083-evolution
BINARY_PATH = [
    ("v3 binary MLP", 0.21, 0.96),
    ("v5 NeKo + weighted loss", 0.34, 0.27),
    ("v6 XGBoost 300 trees", 0.34, 0.59),
    ("v7 + persistence prior", 0.47, 0.21),
]

# Three-class YES operating points, tab:three_class (20-day holdout)
# (label, precision, recall, marker, color, annotation offset)
THREE_CLASS = [
    ("XGB, $P\\geq0.30$", 0.821, 0.418, "o", "#b2182b", (8, 4)),
    ("XGB, $P\\geq0.50$", 0.792, 0.346, "s", "#d6604d", (-30, -16)),
    ("NeKo-PIGNN (YES)", 0.917, 0.127, "D", "#ef8a62", (8, 4)),
]

# Abstention coverage and operational season point
COVERAGE = ("YES+UNCERTAIN coverage", 0.82, 0.88)          # tab:alert-levels
OPERATIONAL = ("Dry season 2025 (184 d)", 0.842, 0.918)    # tab:extended-temporal


def main() -> None:
    fig, ax = plt.subplots(figsize=(6.6, 4.8), dpi=300)

    # Iso-F1 contours
    for f1 in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        r = np.linspace(0.01, 1.0, 400)
        p = f1 * r / np.clip(2 * r - f1, 1e-9, None)
        mask = (p > 0) & (p <= 1.02) & (2 * r - f1 > 0)
        ax.plot(r[mask], p[mask], ls=":", lw=0.6, color="0.8", zorder=1)
        idx = np.argmin(np.abs(r - 0.995))
        if mask[idx] and 0.05 < p[idx] < 1.0:
            ax.annotate(f"F1={f1:.1f}", (1.005, p[idx]), fontsize=6.5,
                        color="0.55", va="center")

    # Binary iteration path with arrows
    bx = [r for _, _, r in BINARY_PATH]
    by = [p for _, p, _ in BINARY_PATH]
    ax.plot(bx, by, lw=1.0, color="0.55", zorder=2, alpha=0.8)
    for i in range(len(bx) - 1):
        ax.annotate("", xy=(bx[i + 1], by[i + 1]), xytext=(bx[i], by[i]),
                    arrowprops=dict(arrowstyle="-|>", color="0.45", lw=1.0),
                    zorder=2)
    for label, p, r in BINARY_PATH:
        ax.scatter(r, p, marker="v", s=45, color="0.45", edgecolor="k",
                   lw=0.5, zorder=3)
        offset = (6, -11) if "v6" in label else (6, 5)
        ax.annotate(label, (r, p), textcoords="offset points",
                    xytext=offset, fontsize=7, color="0.25")

    # Three-class YES alerts
    for label, p, r, marker, color, offset in THREE_CLASS:
        ax.scatter(r, p, marker=marker, s=60, color=color, edgecolor="k",
                   lw=0.6, zorder=4)
        ax.annotate(label, (r, p), textcoords="offset points",
                    xytext=offset, fontsize=7.5, color="#67001f")

    # Coverage (abstention) and operational season points
    label, p, r = COVERAGE
    ax.scatter(r, p, marker="*", s=190, color="#f4a582", edgecolor="k",
               lw=0.7, zorder=5)
    ax.annotate(label, (r, p), textcoords="offset points", xytext=(-118, -4),
                fontsize=7.5, color="#67001f")

    label, p, r = OPERATIONAL
    ax.scatter(r, p, marker="*", s=190, color="#b2182b", edgecolor="k",
               lw=0.7, zorder=5)
    ax.annotate(label, (r, p), textcoords="offset points", xytext=(-70, 12),
                fontsize=7.5, color="#67001f")

    # Legend proxies
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="v", ls="-", color="0.45", markeredgecolor="k",
               markersize=6, lw=1.0, label="Binary detection (v3--v7)"),
        Line2D([], [], marker="o", ls="", color="#b2182b", markeredgecolor="k",
               markersize=7, label="Three-class YES alert (v8/v9)"),
        Line2D([], [], marker="*", ls="", color="#b2182b", markeredgecolor="k",
               markersize=12, label="Operational / abstention coverage"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, framealpha=0.95)

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.2, lw=0.4)
    fig.tight_layout()

    FIGURES_DIR.mkdir(exist_ok=True)
    out_png = FIGURES_DIR / "pr-operating-points.png"
    fig.savefig(out_png, bbox_inches="tight")
    print(f"Saved {out_png}")


if __name__ == "__main__":
    main()
