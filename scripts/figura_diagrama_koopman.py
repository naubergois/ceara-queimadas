#!/usr/bin/env python3
"""Gera figura de qualidade de publicação: diagrama NeKo-PIGNN."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

fig, ax = plt.subplots(1, 1, figsize=(16, 10))
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis('off')

C_BG = '#1a1a2e'; C_BOX = '#16213e'; C_BOX2 = '#0f3460'
C_GOLD = '#f5c518'; C_GREEN = '#4ecca3'; C_BLUE = '#4361ee'
C_PURPLE = '#7b2cbf'; C_TEXT = '#ffffff'; C_TEXT2 = '#cccccc'
C_ACCENT = '#e94560'

fig.patch.set_facecolor(C_BG); ax.set_facecolor(C_BG)

def draw_box(ax, x, y, w, h, color, text, subtext='', fs=14, sfs=9):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                         facecolor=color, edgecolor='white', linewidth=1.5, alpha=0.9)
    ax.add_patch(box)
    ax.text(x+w/2, y+h/2+0.12, text, ha='center', va='center',
            fontsize=fs, fontweight='bold', color=C_TEXT)
    if subtext:
        for i, line in enumerate(subtext.split('\n')):
            ax.text(x+w/2, y+h/2-0.30-i*0.28, line, ha='center', va='center',
                    fontsize=sfs, color=C_TEXT2)

def draw_arrow(ax, x1, y1, x2, y2, color='white', lw=2.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                connectionstyle='arc3,rad=0.12'))

fig.text(0.5, 0.96, "Neural Koopman Operator + Physics-Informed GNN — Arquitetura NeKo-PIGNN",
         ha='center', fontsize=18, fontweight='bold', color='white', transform=fig.transFigure)
fig.text(0.5, 0.925, "g(zₜ₊₁) = K · g(zₜ) + ∂u/∂t = D∇²u + R(θ,u,w) + L = L_data + λ·L_PDE",
         ha='center', fontsize=11, color=C_GOLD, family='monospace', transform=fig.transFigure)

# BLOCO 1: Dados
draw_box(ax, 0.5, 4.5, 2.5, 2.0, C_BOX2, "📡 Dados de Satélite",
         "VIIRS (375m)\nGOES-16 CH02/05/07\nINPE | NASA FIRMS\n2024-2026", fs=12, sfs=8)
draw_arrow(ax, 3.0, 5.7, 4.3, 5.7)

# BLOCO 2: Pré-processamento
draw_box(ax, 4.3, 4.8, 2.0, 1.4, C_BOX, "🔧 Pré-processamento",
         "Normalização\nK-Means Clustering\nFusão GOES+VIIRS\nFiltro Outlier", fs=11, sfs=8)
draw_arrow(ax, 6.3, 5.7, 7.5, 5.7, C_GOLD)

# BLOCO 3: Autoencoder
draw_box(ax, 7.5, 4.0, 2.8, 3.4, '#1b2a4a', "🧠 Autoencoder Variacional",
         "EncoderMLP: x → z\nDecoderMLP: z → x̂\nObserváveis Koopman: g(z)\nLatent dim: d=32", fs=12, sfs=8)
# Caixa latente
lat = FancyBboxPatch((8.0, 4.4), 1.8, 0.65, boxstyle="round,pad=0.1",
                      facecolor=C_BLUE, edgecolor=C_GOLD, linewidth=2, alpha=0.8)
ax.add_patch(lat)
ax.text(8.9, 4.72, "zₜ ∈ ℝᵈ", ha='center', va='center', fontsize=11, fontweight='bold', color='white')

draw_arrow(ax, 10.3, 5.7, 11.5, 6.8, C_GOLD)

# BLOCO 4: Koopman
draw_box(ax, 11.5, 6.2, 3.2, 1.8, C_GOLD, "🔄 Operador Koopman (K)",
         "g(zₜ₊₁) = K · g(zₜ)\nK = U·Vᵀ (low-rank)\nPropagação n-passos\nModos Coerentes (DMD)", fs=12, sfs=8)

draw_arrow(ax, 13.1, 6.2, 13.1, 4.5, C_GREEN)
draw_arrow(ax, 10.3, 4.0, 11.5, 3.2, C_GREEN, lw=2.5)

# BLOCO 5: PI-GNN
draw_box(ax, 11.5, 2.4, 3.2, 2.2, C_GREEN, "🌐 PI-GNN (Rothermel)",
         "FireMessagePassing\nAtenção Direcional (vento)\nEncoder → MP(4) → Decoder\nSkip Connections", fs=12, sfs=8)

draw_arrow(ax, 13.1, 2.4, 13.1, 0.5, C_PURPLE)

# BLOCO 6: Loss
draw_box(ax, 11.5, 0.2, 3.2, 1.2, C_PURPLE, "📉 Função de Perda Total",
         "L_recon + L_KL + L_pred  +  L_GNN  +  λ·L_PDE(Rothermel)", fs=11, sfs=8)

# Brace modelo híbrido
brace = FancyBboxPatch((11.0, 0.0), 4.2, 8.5, boxstyle="round,pad=0.08",
                        facecolor=C_GOLD, edgecolor='none', alpha=0.08)
ax.add_patch(brace)
ax.text(15.3, 4.25, "NeKo-PIGNN\n(Modelo Híbrido)", ha='center', va='center',
        fontsize=11, fontweight='bold', color=C_GOLD, rotation=90)

# Legenda
leg = ax.legend(
    handles=[
        mpatches.Patch(facecolor=C_BOX2, edgecolor='white', label='Dados Entrada'),
        mpatches.Patch(facecolor=C_BOX, edgecolor='white', label='Pré-processamento'),
        mpatches.Patch(facecolor='#1b2a4a', edgecolor='white', label='Autoencoder VAE'),
        mpatches.Patch(facecolor=C_GOLD, edgecolor='white', label='Operador Koopman'),
        mpatches.Patch(facecolor=C_GREEN, edgecolor='white', label='PI-GNN / Rothermel'),
        mpatches.Patch(facecolor=C_PURPLE, edgecolor='white', label='Função de Perda'),
    ],
    loc='lower left', fontsize=8, framealpha=0.8, facecolor='#111122',
    edgecolor='white', labelcolor='white',
    title='Componentes', title_fontsize=9
)

ax.text(0.5, 0.02, "VIIRS/GOES-16 → Autoencoder → Espaço Koopman → PI-GNN → Previsão + Perda Física (Rothermel 1972)",
        ha='center', va='center', fontsize=8, color='#666666', fontstyle='italic',
        transform=ax.transData)

plt.tight_layout(rect=[0, 0, 1, 0.9])
out = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/figures/diagrama-koopman-pignn.png'
plt.savefig(out, dpi=250, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.close()
print(f"✅ Figura salva: {out}")
print(f"   Tamanho: {os.path.getsize(out)/1024:.0f} KB")
