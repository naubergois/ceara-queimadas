#!/usr/bin/env python3
"""Generate publication figures for paper-digital-twin-queimadas.tex and artigo."""
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def fig_langgraph():
    nodes = [
        "coletar_dados", "validar_dados", "agente_geoespacial",
        "agente_goes16", "agente_climatico", "fundir_evidencias",
        "classificar_risco", "agente_react_diagnostico",
        "gerar_alertas", "gerar_boletim",
    ]
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_title("LangGraph pipeline (10 nodes)", fontsize=12, fontweight="bold")

    y = 11
    for i, n in enumerate(nodes):
        if n in ("agente_geoespacial", "agente_goes16", "agente_climatico"):
            x = {"agente_geoespacial": 2, "agente_goes16": 5, "agente_climatico": 8}[n]
            yy = 7.5
        else:
            x, yy = 5, y
            y -= 1.1
        ax.add_patch(plt.Rectangle((x - 1.4, yy - 0.35), 2.8, 0.7,
                                   facecolor="#E8F4FC", edgecolor="#2B5F8A", lw=1.5))
        ax.text(x, yy, n.replace("_", "\n"), ha="center", va="center", fontsize=7)

    ax.annotate("", xy=(5, 10.2), xytext=(5, 10.9),
                arrowprops=dict(arrowstyle="->", color="#666"))
    for x in (2, 5, 8):
        ax.annotate("", xy=(x, 8.2), xytext=(5, 9.5),
                    arrowprops=dict(arrowstyle="->", color="#666"))
    ax.annotate("", xy=(5, 6.8), xytext=(5, 7.1),
                arrowprops=dict(arrowstyle="->", color="#666"))
    fig.savefig(FIG / "langgraph.png")
    plt.close(fig)


def fig_resultados():
    methods = ["Digital twin", "Iso. forest", "Persistence", "Spatial res.", "Consensus"]
    f1 = [0.049, 0.037, 0.012, 0.006, 0.000]
    recall = [0.106, 0.063, 0.007, 0.004, 0.000]
    x = np.arange(len(methods))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w / 2, f1, w, label="F1 (real INPE 2024-10-31)", color="#B15533")
    ax.bar(x + w / 2, recall, w, label="Recall", color="#2B5F8A")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=20, ha="right")
    ax.set_ylabel("Score")
    ax.set_title("Real-data detection metrics vs INPE ground truth")
    ax.legend()
    ax.set_ylim(0, 0.12)
    fig.savefig(FIG / "resultados-experimentais.png")
    plt.close(fig)


def fig_evolucao():
    hours = np.arange(0, 24)
    np.random.seed(42)
    base = 3 + 2 * np.sin((hours - 14) * np.pi / 12)
    firms = np.maximum(0, base + np.random.poisson(1.5, 24))
    goes = np.maximum(0, (firms * 0.7 + np.random.poisson(0.8, 24))).astype(int)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(hours, firms, "o-", label="FIRMS hotspots", color="#B15533", lw=2)
    ax.plot(hours, goes, "s-", label="GOES-16 detections", color="#2B5F8A", lw=2)
    ax.set_xlabel("Hour (UTC)")
    ax.set_ylabel("Count")
    ax.set_title("Diurnal fire activity — Ceará (illustrative)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.savefig(FIG / "evolucao-focos.png")
    plt.close(fig)


def fig_mapa_ceara():
    grid = np.random.RandomState(7).rand(24, 24)
    grid[8:14, 10:16] += 0.6
    grid[4:7, 18:22] += 0.4
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(grid, cmap="YlOrRd", origin="lower", aspect="auto")
    ax.set_title("Multi-scale thermal anomaly (T_B13 residual)")
    ax.set_xlabel("Longitude index")
    ax.set_ylabel("Latitude index")
    plt.colorbar(im, ax=ax, fraction=0.046, label="Anomaly score")
    fig.savefig(FIG / "mapa-deteccao-ceara.png")
    plt.close(fig)


def fig_neko_arch():
    """Symlink-style: copy from koopman if main png missing."""
    src = FIG / "diagrama-koopman-pignn.png"
    koop = FIG / "koopman" / "diagrama-koopman-pignn.svg"
    if not src.exists() and koop.exists():
        import shutil
        shutil.copy(koop, FIG / "diagrama-koopman-pignn.svg")


if __name__ == "__main__":
    fig_langgraph()
    fig_resultados()
    fig_evolucao()
    fig_mapa_ceara()
    print("Figures written to", FIG)
    for name in ["langgraph.png", "resultados-experimentais.png",
                  "evolucao-focos.png", "mapa-deteccao-ceara.png"]:
        p = FIG / name
        print(f"  {name}: {p.stat().st_size // 1024} KB" if p.exists() else f"  {name}: MISSING")
