#!/usr/bin/env python3
"""
Diagrama NeKo-PIGNN — versao deterministica (consistente com o artigo EN).

Substitui o bloco "Variational Autoencoder" da v2 por um autoencoder
deterministico (KoopmanAE), remove a perda KL e alinha as equacoes com a
metodologia publicada:
  - z_{t+1} = K · z_t                          (dinamica linear latente)
  - K = U · V^T (low-rank, r = 16)             (fatoracao de baixo posto)
  - L_koop = L_recon + a1·L_1-step + a2·L_multi + L_spec
  - L_spec = max(0, rho(K) - 1 + eps)          (estabilidade espectral)
  - L_PIGNN = BCE + l1·L_AE + l2·L_phys + l3·L2
  - Curriculo em duas fases (warm-up -> physics ramp-up)

Saida: figures/diagrama-koopman-pignn-deterministic.png (300 DPI)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import os

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'mathtext.fontset': 'dejavusans',
    'mathtext.default': 'regular',
    'axes.edgecolor': '#cccccc',
    'axes.facecolor': '#ffffff',
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

C_BG      = '#FAFBFC'
C_SAT     = '#2B5F8A'
C_PREPROC = '#5A8F7B'
C_AE      = '#3A6EA5'
C_KOOP    = '#B15533'
C_GNN     = '#4A7B6E'
C_LOSS    = '#8B3A62'
C_OUTPUT  = '#2E5E3B'
C_BORDER  = '#333333'
C_TEXT    = '#222222'
C_TEXT2   = '#555555'
C_GOLD    = '#B8860B'
C_ARROW   = '#666666'
C_HIGHLIGHT = '#E8D5B7'

FIG_W = 18
FIG_H = 11


def round_box(ax, x, y, w, h, color, edgecolor=C_BORDER, lw=1.5, alpha=0.92):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.18",
                         facecolor=color, edgecolor=edgecolor,
                         linewidth=lw, alpha=alpha)
    ax.add_patch(box)
    return box


def draw_arrow(ax, x1, y1, x2, y2, color=C_ARROW, lw=2.0, style='arc3,rad=0.08'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                connectionstyle=style, shrinkA=6, shrinkB=6))


def draw_arrow_label(ax, x, y, label, fontsize=8, color=C_TEXT2):
    ax.text(x, y, label, ha='center', va='bottom', fontsize=fontsize,
            color=color, style='italic')


fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis('off')
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ------------------------------------------------------------------
# Titulo e barra de equacoes
# ------------------------------------------------------------------
ax.text(FIG_W/2, FIG_H - 0.30,
        "Neural Koopman Operator + Physics-Informed GNN  |  NeKo-PIGNN Architecture",
        ha='center', va='center', fontsize=19, fontweight='bold', color=C_TEXT,
        family='sans-serif')

eq_bar = (
    r"$\mathbf{z}_{t+1} = \mathbf{K} \cdot \mathbf{z}_t$"
    r"   $\Longrightarrow$   "
    r"$\dfrac{\partial u}{\partial t} = D\nabla^2 u + R(\theta, u, w)$"
    r"   $\Longrightarrow$   "
    r"$\mathcal{L}_{\text{koop}} = \mathcal{L}_{\text{recon}}"
    r" + \alpha_1\mathcal{L}_{\text{1step}}"
    r" + \alpha_2\mathcal{L}_{\text{multi}}"
    r" + \mathcal{L}_{\text{spec}}$"
)
ax.text(FIG_W/2, FIG_H - 0.70, eq_bar,
        ha='center', va='center', fontsize=11, color=C_GOLD,
        family='serif', style='italic')

# ------------------------------------------------------------------
# Bloco 1 — Dados de satelite
# ------------------------------------------------------------------
x1, y1, w1, h1 = 0.8, 7.2, 3.2, 1.8
round_box(ax, x1, y1, w1, h1, C_SAT)
ax.text(x1 + w1/2, y1 + h1 - 0.35, "Satellite Data", ha='center', va='center',
        fontsize=13, color='white', fontweight='bold')
for i, txt in enumerate([
    "VIIRS S-NPP / NOAA-20 (375m)",
    "GOES-16 CH02/05/07 (1km)",
    "INPE BDQueimadas · NASA FIRMS",
    "Weather: wind, moisture, slope",
]):
    ax.text(x1 + w1/2, y1 + h1 - 0.70 - i*0.25, txt, ha='center', va='center',
            fontsize=9, color='#d0d8e8')

# ------------------------------------------------------------------
# Bloco 2 — Pre-processamento
# ------------------------------------------------------------------
x2, y2, w2, h2 = 5.0, 7.5, 2.8, 1.5
round_box(ax, x2, y2, w2, h2, C_PREPROC)
ax.text(x2 + w2/2, y2 + h2 - 0.30, "Preprocessing", ha='center', va='center',
        fontsize=13, color='white', fontweight='bold')
for i, txt in enumerate([
    "Cloud masking · DQF filter",
    "K-Means clustering (GOES)",
    "VIIRS + GOES fusion",
]):
    ax.text(x2 + w2/2, y2 + h2 - 0.60 - i*0.25, txt, ha='center', va='center',
            fontsize=9, color='#d0e0d8')

draw_arrow(ax, x1 + w1, y1 + h1*0.5, x2, y2 + h2*0.5)
draw_arrow_label(ax, (x1 + w1 + x2)/2, y1 + h1*0.5 + 0.15,
                 "Feature extraction", fontsize=8)

# ------------------------------------------------------------------
# Bloco 3 — Koopman Autoencoder (deterministico)
# ------------------------------------------------------------------
x3, y3, w3, h3 = 0.8, 4.0, 3.2, 2.8
round_box(ax, x3, y3, w3, h3, C_AE)
ax.text(x3 + w3/2, y3 + h3 - 0.30, "Koopman Autoencoder",
        ha='center', va='center', fontsize=13, color='white', fontweight='bold')
ax.text(x3 + w3/2, y3 + h3 - 0.62, "deterministic encoder\u2013decoder",
        ha='center', va='center', fontsize=9, color='#d0dce8', style='italic')
ax.text(x3 + w3/2, y3 + h3 - 0.90,
        r"Encoder $g_\phi$:  $\mathbf{x}_t \rightarrow \mathbf{z}_t$   (512-256-128)",
        ha='center', va='center', fontsize=9, color='#d0dce8')
ax.text(x3 + w3/2, y3 + h3 - 1.15,
        r"Decoder $h_\psi$:  $\mathbf{z}_t \rightarrow \hat{\mathbf{x}}_t$",
        ha='center', va='center', fontsize=9, color='#d0dce8')
ax.text(x3 + w3/2, y3 + h3 - 1.45, "Koopman observables:",
        ha='center', va='center', fontsize=10, color='#e0e8f0', fontweight='bold')
ax.text(x3 + w3/2, y3 + h3 - 1.72,
        r"$\mathbf{z}_t = g_\phi(\mathbf{x}_t) \in \mathbb{R}^{64}$",
        ha='center', va='center', fontsize=11, color=C_GOLD,
        family='serif', style='italic')

lat_x, lat_y = x3 + 0.30, y3 + 0.25
lat_w, lat_h = w3 - 0.60, 0.50
round_box(ax, lat_x, lat_y, lat_w, lat_h, '#1a3a5c', edgecolor=C_GOLD, lw=1.8, alpha=0.9)
ax.text(lat_x + lat_w/2, lat_y + lat_h/2,
        r"$\mathbf{x}_t \in \mathbb{R}^{140}$  (7 vars $\times$ 20 cells)",
        ha='center', va='center', fontsize=9, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')

draw_arrow(ax, x2 + w2/2, y2, x3 + w3/2, y3 + h3)
draw_arrow_label(ax, (x2 + w2/2 + x3 + w3/2)/2, (y2 + y3 + h3)/2,
                 "State encoding", fontsize=8)

# ------------------------------------------------------------------
# Bloco 4 — Operador de Koopman
# ------------------------------------------------------------------
x4, y4, w4, h4 = 5.0, 4.0, 3.8, 2.8
round_box(ax, x4, y4, w4, h4, C_KOOP)
ax.text(x4 + w4/2, y4 + h4 - 0.25, "Koopman Operator  (K)",
        ha='center', va='center', fontsize=14, color='white', fontweight='bold')
ax.text(x4 + w4/2, y4 + h4 - 0.70,
        r"$\mathbf{z}_{t+1} = \mathbf{K}_\theta \cdot \mathbf{z}_t$",
        ha='center', va='center', fontsize=12, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')
ax.text(x4 + w4/2, y4 + h4 - 1.10, "Low-rank matrix:",
        ha='center', va='center', fontsize=10, color='#e8d0c0')
ax.text(x4 + w4/2, y4 + h4 - 1.40,
        r"$\mathbf{K} = \mathbf{U} \cdot \mathbf{V}^{\top} \quad (r=16)$",
        ha='center', va='center', fontsize=12, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')
ax.text(x4 + w4/2, y4 + h4 - 1.80, "Spectral stability:",
        ha='center', va='center', fontsize=10, color='#e8d0c0')
ax.text(x4 + w4/2, y4 + h4 - 2.10,
        r"$\mathcal{L}_{\text{spec}} = \max(0,\, \rho(\mathbf{K}_\theta) - 1 + \epsilon)$",
        ha='center', va='center', fontsize=10, color='#e8d8c8',
        family='serif', style='italic')
ax.text(x4 + w4/2, y4 + h4 - 2.45, "Coherent modes: DMD spectral decomposition",
        ha='center', va='center', fontsize=8, color='#d0c0a0')

draw_arrow(ax, x3 + w3, y3 + h3*0.65, x4, y4 + h4*0.65)
draw_arrow_label(ax, (x3 + w3 + x4)/2, y3 + h3*0.65 + 0.15,
                 r"$\mathbf{z}_t$", fontsize=9)

# ------------------------------------------------------------------
# Bloco 5 — PI-GNN
# ------------------------------------------------------------------
x5, y5, w5, h5 = 10.5, 4.0, 3.8, 2.8
round_box(ax, x5, y5, w5, h5, C_GNN)
ax.text(x5 + w5/2, y5 + h5 - 0.25, "Physics-Informed GNN",
        ha='center', va='center', fontsize=14, color='white', fontweight='bold')
for i, txt in enumerate([
    "Spatial propagation on graph",
    "GCNConv (3 layers, 128 ch.)",
    "Directional attention (wind)",
    "Skip connections · LayerNorm",
]):
    ax.text(x5 + w5/2, y5 + h5 - 0.65 - i*0.30, txt, ha='center', va='center',
            fontsize=9, color='#d0e8e0')
ax.text(x5 + w5/2, y5 + h5 - 1.95, "PDE residual:",
        ha='center', va='center', fontsize=10, color='#e0e8e0', fontweight='bold')
ax.text(x5 + w5/2, y5 + h5 - 2.25,
        r"$\dfrac{\partial u}{\partial t} - D\nabla^2 u - R(\theta,u,w)$",
        ha='center', va='center', fontsize=11, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')

draw_arrow(ax, x4 + w4, y4 + h4*0.65, x5, y5 + h5*0.65)
draw_arrow_label(ax, (x4 + w4 + x5)/2, y4 + h4*0.65 + 0.20,
                 r"$\mathbf{z}_{t+1}$ (latent)", fontsize=8)

# ------------------------------------------------------------------
# Bloco 6 — Saida
# ------------------------------------------------------------------
x7, y7, w7, h7 = 10.5, 7.2, 3.8, 1.8
round_box(ax, x7, y7, w7, h7, C_OUTPUT)
ax.text(x7 + w7/2, y7 + h7 - 0.30, "Prediction Output",
        ha='center', va='center', fontsize=13, color='white', fontweight='bold')
for i, txt in enumerate([
    "û(t+1) = predicted fire state",
    "FRP · Temperature · Spread rate",
    "Risk index · Coherent modes",
]):
    ax.text(x7 + w7/2, y7 + h7 - 0.65 - i*0.28, txt, ha='center', va='center',
            fontsize=9, color='#c0e0c8')

draw_arrow(ax, x5 + w5/2, y5 + h5, x7 + w7/2, y7, lw=2.0, color=C_GOLD,
           style='arc3,rad=0.12')
decoder_x = (x5 + w5/2 + x7 + w7/2)/2
decoder_y = (y5 + h5 + y7)/2 + 0.1
ax.plot(decoder_x, decoder_y, 'o', color=C_GOLD, markersize=6)
ax.text(decoder_x, decoder_y + 0.25, r"Decoder $h_\psi$: $\hat{\mathbf{z}} \rightarrow \hat{\mathbf{x}}$",
        ha='center', va='center', fontsize=8, color=C_GOLD)

# ------------------------------------------------------------------
# Bloco 7 — Funcao de perda
# ------------------------------------------------------------------
x6, y6, w6, h6 = 0.8, 0.35, 11.2, 3.0
round_box(ax, x6, y6, w6, h6, '#EEF0F3', edgecolor='#999999', lw=1.0, alpha=0.4)
ax.text(x6 + 0.4, y6 + h6 - 0.30, "Loss Functions (two-phase curriculum)",
        ha='left', va='center', fontsize=12, color=C_TEXT, fontweight='bold')

loss_items = [
    (0.8, y6 + h6 - 0.78,
     r"\mathcal{L}_{\text{recon}} = \|\mathbf{x}_t - h_\psi(g_\phi(\mathbf{x}_t))\|^2",
     "Reconstruction"),
    (0.8, y6 + h6 - 1.26,
     r"\mathcal{L}_{\text{1step}} = \|\mathbf{x}_{t+1} - h_\psi(\mathbf{K}_\theta\, g_\phi(\mathbf{x}_t))\|^2",
     "1-step prediction"),
    (0.8, y6 + h6 - 1.74,
     r"\mathcal{L}_{\text{multi}} = \sum_k \|\mathbf{x}_{t+k} - h_\psi(\mathbf{K}_\theta^k\, g_\phi(\mathbf{x}_t))\|^2",
     "Multi-step prediction"),
    (6.2, y6 + h6 - 0.78,
     r"\mathcal{L}_{\text{spec}} = \max(0,\, \rho(\mathbf{K}_\theta) - 1 + \epsilon)",
     "Spectral stability"),
    (6.2, y6 + h6 - 1.26,
     r"\mathcal{L}_{\text{phys}} = \|\frac{\partial u}{\partial t} - D\nabla^2 u - R(\theta, u, w)\|^2",
     "Physics (Rothermel)"),
    (6.2, y6 + h6 - 1.74,
     r"\mathcal{L}_{\text{PIGNN}} = \mathrm{BCE} + \lambda_1\mathcal{L}_{\text{AE}} + \lambda_2\mathcal{L}_{\text{phys}} + \lambda_3\|\mathbf{W}\|_2",
     "PI-GNN total"),
]
for lx, ly, eq, label in loss_items:
    ax.text(lx + 5.6, ly + 0.06, f"${eq}$", ha='center', va='center',
            fontsize=9, color=C_TEXT, family='serif', style='italic')
    ax.text(lx + 5.6, ly - 0.20, f"— {label}", ha='center', va='center',
            fontsize=7, color=C_TEXT2)

total_eq_y = y6 + 0.12
round_box(ax, x6 + 1.4, total_eq_y, w6 - 2.8, 0.55, C_HIGHLIGHT,
          edgecolor=C_LOSS, lw=1.8, alpha=0.9)
ax.text(x6 + w6/2, total_eq_y + 0.28,
        r"Phase 1: $\mathcal{L}_{\text{recon}} + \alpha_1\mathcal{L}_{\text{1step}}$ (warm-up)"
        r"$\;\;\longrightarrow\;\;$"
        r"Phase 2: $+\,\alpha_2\mathcal{L}_{\text{multi}} + \mathcal{L}_{\text{spec}} + \lambda_{\text{PDE}}\mathcal{L}_{\text{phys}}$ (ramp-up)",
        ha='center', va='center', fontsize=10, color=C_LOSS,
        fontweight='bold', family='serif')

# ------------------------------------------------------------------
# Setas adicionais
# ------------------------------------------------------------------
draw_arrow(ax, x2 + w2, y2 + h2*0.3, x7, y7 + h7*0.3,
           color='#aaaaaa', lw=1.2, style='arc3,rad=-0.3')
ax.text((x2 + w2 + x7)/2, (y2 + h2*0.3 + y7 + h7*0.3)/2 + 0.15,
        "Skip connection", ha='center', va='center', fontsize=7,
        color='#999999', style='italic')

draw_arrow(ax, x6 + 2.5, y6 + h6, x4 + 0.5, y4, lw=1.5, color=C_LOSS,
           style='arc3,rad=0.25')
ax.text(4.85, 3.62, r"Backprop (loss $\rightarrow$ K)",
        ha='center', va='center', fontsize=8, color=C_LOSS)

# ------------------------------------------------------------------
# Equacoes de Rothermel
# ------------------------------------------------------------------
roth_x, roth_y, roth_w, roth_h = 15.2, 7.5, 2.5, 1.5
round_box(ax, roth_x, roth_y, roth_w, roth_h, '#FEF8E7', edgecolor=C_GOLD, lw=1.2, alpha=0.9)
ax.text(roth_x + roth_w/2, roth_y + roth_h - 0.20, "Rothermel (1972)",
        ha='center', va='center', fontsize=9, color=C_GOLD, fontweight='bold')
ax.text(roth_x + roth_w/2, roth_y + roth_h - 0.50,
        r"$R = R_0 (1 + \phi_w + \phi_s)$",
        ha='center', va='center', fontsize=10, fontweight='bold',
        family='serif', style='italic')
ax.text(roth_x + roth_w/2, roth_y + roth_h - 0.80,
        r"$\phi_w = 0.2 \, U^{1.5} \, \eta_M$",
        ha='center', va='center', fontsize=9, family='serif', style='italic')
ax.text(roth_x + roth_w/2, roth_y + roth_h - 1.05,
        r"$\phi_s = 0.5 \tan^2(\theta)$",
        ha='center', va='center', fontsize=9, family='serif', style='italic')
ax.text(roth_x + roth_w/2, roth_y + roth_h - 1.25,
        "η_M = exp(−5 · fuel_moisture)",
        ha='center', va='center', fontsize=8, color=C_TEXT2)

draw_arrow(ax, roth_x, roth_y + roth_h*0.5, x5 + w5, y5 + h5*0.6,
           color=C_GOLD, lw=1.2, style='arc3,rad=0.2')
ax.text((roth_x + x5 + w5)/2 - 0.3, (roth_y + roth_h*0.5 + y5 + h5*0.6)/2 + 0.1,
        "Physics regularization", ha='center', va='center', fontsize=7, color=C_GOLD)

# ------------------------------------------------------------------
# Legenda e rodape
# ------------------------------------------------------------------
legend_elements = [
    mpatches.Patch(facecolor=C_SAT, edgecolor=C_BORDER, label='Satellite Data'),
    mpatches.Patch(facecolor=C_PREPROC, edgecolor=C_BORDER, label='Preprocessing'),
    mpatches.Patch(facecolor=C_AE, edgecolor=C_BORDER, label='Koopman Autoencoder'),
    mpatches.Patch(facecolor=C_KOOP, edgecolor=C_BORDER, label='Koopman Operator (K)'),
    mpatches.Patch(facecolor=C_GNN, edgecolor=C_BORDER, label='Physics-Informed GNN'),
    mpatches.Patch(facecolor=C_OUTPUT, edgecolor=C_BORDER, label='Prediction'),
    mpatches.Patch(facecolor=C_HIGHLIGHT, edgecolor=C_GOLD, label='Loss / Curriculum'),
]
leg = ax.legend(handles=legend_elements, loc='upper center', fontsize=8, ncol=7,
                framealpha=0.85, facecolor=C_BG, edgecolor='#CCCCCC',
                labelcolor=C_TEXT, title='Components', title_fontsize=9,
                bbox_to_anchor=(0.5, -0.005))
leg.get_title().set_fontweight('bold')

ax.text(FIG_W/2, -0.85,
        r"Data flow: VIIRS/GOES $\rightarrow$ Preprocessing $\rightarrow$ KoopmanAE encoder (observables)"
        r" $\rightarrow$ K matrix $\rightarrow$ PI-GNN (Rothermel) $\rightarrow$ Decoder $\rightarrow$ Prediction",
        ha='center', va='center', fontsize=8, color='#999999', style='italic')

# ------------------------------------------------------------------
# Salvar
# ------------------------------------------------------------------
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'figures', 'diagrama-koopman-pignn-deterministic.png')
plt.savefig(out, dpi=300, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.close()
print(f"Saved {out} ({os.path.getsize(out)/1024:.0f} KB)")
