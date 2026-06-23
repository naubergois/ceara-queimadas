#!/usr/bin/env python3
"""
INOV-006: Diagrama Matemático do Operador de Koopman Neural + PI-GNN
=====================================================================
Gera figura de qualidade de PUBLICACAO CIENTIFICA (300 DPI)
Ilustrando o fluxo completo: VIIRS → VAE → Espaço Koopman → Matriz K → PI-GNN → Previsão

Equações na figura:
  (1) g(z_{t+1}) = K · g(z_t)            — Koopman linear dynamics
  (2) K = U · V^T                         — Low-rank factorization
  (3) ∂u/∂t = D∇²u + R(θ,u,w)            — Reaction-diffusion (PDE)
  (4) L_total = L_recon + βL_KL + αL_pred + λGNN·LGNN + λPDE·LPDE  — Total loss
  (5) R = R0(1 + φw + φs)                — Rothermel spread rate
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

# ============================================================================
# Configurações de estilo profissional
# ============================================================================
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

# Paleta de cores profissional
C_BG      = '#FAFBFC'      # fundo claro (artigo impresso)
C_SAT     = '#2B5F8A'      # azul escuro — dados de satélite
C_PREPROC = '#5A8F7B'      # verde musgo — pré-processamento
C_VAE     = '#3A6EA5'      # azul médio — autoencoder
C_KOOP    = '#B15533'      # terracota — operador Koopman
C_GNN     = '#4A7B6E'      # verde escuro — PI-GNN
C_LOSS    = '#8B3A62'      # vinho — função de perda
C_OUTPUT  = '#2E5E3B'      # verde floresta — saída
C_BORDER  = '#333333'
C_TEXT    = '#222222'
C_TEXT2   = '#555555'
C_GOLD    = '#B8860B'
C_ARROW   = '#666666'
C_HIGHLIGHT = '#E8D5B7'    # fundo destacado para equações

FIG_W = 18  # polegadas
FIG_H = 11

# ============================================================================
# Funções auxiliares
# ============================================================================

def round_box(ax, x, y, w, h, color, edgecolor=C_BORDER, lw=1.5, alpha=0.92):
    """Desenha caixa com cantos arredondados."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.18",
        facecolor=color, edgecolor=edgecolor,
        linewidth=lw, alpha=alpha,
    )
    ax.add_patch(box)
    return box

def draw_text(ax, x, y, text, fontsize=11, color=C_TEXT, weight='normal',
              ha='center', va='center', family=None, style='normal'):
    """Desenha texto."""
    ax.text(x, y, text, ha=ha, va=va, fontsize=fontsize,
            color=color, fontweight=weight, family=family, style=style)

def draw_math(ax, x, y, text, fontsize=11, color=C_TEXT, weight='normal'):
    """Desenha texto com renderização matemática."""
    ax.text(x, y, f"${text}$", ha='center', va='center', fontsize=fontsize,
            color=color, fontweight=weight, family='serif', style='italic')

def draw_arrow(ax, x1, y1, x2, y2, color=C_ARROW, lw=2.0, style='arc3,rad=0.08',
               head_width=0.25, head_length=0.25):
    """Desenha seta entre dois pontos."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle='->', color=color, lw=lw,
                    connectionstyle=style,
                    shrinkA=6, shrinkB=6,
                ))

def draw_arrow_label(ax, x, y, label, fontsize=8, color=C_TEXT2):
    """Rótulo sobre a seta."""
    ax.text(x, y, label, ha='center', va='bottom', fontsize=fontsize,
            color=color, style='italic')

# ============================================================================
# Criação da figura
# ============================================================================

fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis('off')
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ------------------------------------------------------------------
# TÍTULO
# ------------------------------------------------------------------
ax.text(FIG_W/2, FIG_H - 0.30,
    "Neural Koopman Operator + Physics-Informed GNN  |  NeKo-PIGNN Architecture",
    ha='center', va='center', fontsize=19, fontweight='bold', color=C_TEXT,
    family='sans-serif')

# Barra de equações principais no topo
eq_bar = (
    r"$\mathbf{g}(\mathbf{z}_{t+1}) = \mathbf{K} \cdot \mathbf{g}(\mathbf{z}_t)$"
    r"   $\Longrightarrow$   "
    r"$\dfrac{\partial u}{\partial t} = D\nabla^2 u + R(\theta, u, w)$"
    r"   $\Longrightarrow$   "
    r"$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{recon}}"
    r" + \beta\mathcal{L}_{\text{KL}}"
    r" + \alpha\mathcal{L}_{\text{pred}}"
    r" + \lambda\mathcal{L}_{\text{PDE}}$"
)
ax.text(FIG_W/2, FIG_H - 0.70, eq_bar,
        ha='center', va='center', fontsize=11, color=C_GOLD,
        family='serif', style='italic')

# ------------------------------------------------------------------
# BLOCO 1 — DADOS DE SATÉLITE (x=0.8, y=7.2)
# ------------------------------------------------------------------
x1, y1, w1, h1 = 0.8, 7.2, 3.2, 1.8
round_box(ax, x1, y1, w1, h1, C_SAT, alpha=0.92)
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
# BLOCO 2 — PRÉ-PROCESSAMENTO (x=5.0, y=7.5)
# ------------------------------------------------------------------
x2, y2, w2, h2 = 5.0, 7.5, 2.8, 1.5
round_box(ax, x2, y2, w2, h2, C_PREPROC, alpha=0.92)
ax.text(x2 + w2/2, y2 + h2 - 0.30, "Preprocessing", ha='center', va='center',
        fontsize=13, color='white', fontweight='bold')
for i, txt in enumerate([
    "Cloud masking · DQF filter",
    "K-Means clustering (GOES)",
    "VIIRS + GOES fusion",
]):
    ax.text(x2 + w2/2, y2 + h2 - 0.60 - i*0.25, txt, ha='center', va='center',
            fontsize=9, color='#d0e0d8')

# Seta: Bloco 1 → Bloco 2
draw_arrow(ax, x1 + w1, y1 + h1*0.5, x2, y2 + h2*0.5)
draw_arrow_label(ax, (x1 + w1 + x2)/2, y1 + h1*0.5 + 0.15,
                 "Feature extraction", fontsize=8)

# ------------------------------------------------------------------
# BLOCO 3 — AUTOENCODER VARIACIONAL (x=0.8, y=4.0)
# ------------------------------------------------------------------
x3, y3, w3, h3 = 0.8, 4.0, 3.2, 2.8
round_box(ax, x3, y3, w3, h3, C_VAE, alpha=0.92)
ax.text(x3 + w3/2, y3 + h3 - 0.30, "Variational Autoencoder",
        ha='center', va='center', fontsize=13, color='white', fontweight='bold')
ax.text(x3 + w3/2, y3 + h3 - 0.65, "EncoderMLP:  x → (μ, log σ²) → g(z)",
        ha='center', va='center', fontsize=9, color='#d0dce8')
ax.text(x3 + w3/2, y3 + h3 - 0.90, "DecoderMLP:  g(z) → x̂",
        ha='center', va='center', fontsize=9, color='#d0dce8')
ax.text(x3 + w3/2, y3 + h3 - 1.25, "Observáveis de Koopman:",
        ha='center', va='center', fontsize=10, color='#e0e8f0', fontweight='bold')
ax.text(x3 + w3/2, y3 + h3 - 1.55, r"$\mathbf{g}(\mathbf{z}_t) \in \mathbb{R}^{d}$",
        ha='center', va='center', fontsize=12, color=C_GOLD, family='serif', style='italic')
ax.text(x3 + w3/2, y3 + h3 - 1.90, "Latent dim: d = 32",
        ha='center', va='center', fontsize=9, color='#b0c0d0')

# Caixa destacada para o espaço latente
lat_x = x3 + 0.30
lat_y = y3 + 0.25
lat_w = w3 - 0.60
lat_h = 0.50
round_box(ax, lat_x, lat_y, lat_w, lat_h, '#1a3a5c', edgecolor=C_GOLD, lw=1.8, alpha=0.9)
ax.text(lat_x + lat_w/2, lat_y + lat_h/2,
        r"$\mathbf{g}(\mathbf{z}_t) := \text{Encoder}(\mathbf{x}_t)$",
        ha='center', va='center', fontsize=10, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')

# Seta: Bloco 2 → Bloco 3
draw_arrow(ax, x2 + w2/2, y2, x3 + w3/2, y3 + h3)
draw_arrow_label(ax, (x2 + w2/2 + x3 + w3/2)/2, (y2 + y3 + h3)/2,
                 "VAE encoding", fontsize=8)

# ------------------------------------------------------------------
# BLOCO 4 — OPERADOR DE KOOPMAN (x=5.0, y=4.0)
# ------------------------------------------------------------------
x4, y4, w4, h4 = 5.0, 4.0, 3.8, 2.8
round_box(ax, x4, y4, w4, h4, C_KOOP, alpha=0.92)
ax.text(x4 + w4/2, y4 + h4 - 0.25, "Koopman Operator  (K)",
        ha='center', va='center', fontsize=14, color='white', fontweight='bold')

# Equação principal
ax.text(x4 + w4/2, y4 + h4 - 0.70,
        r"$\mathbf{g}(\mathbf{z}_{t+1}) = \mathbf{K} \cdot \mathbf{g}(\mathbf{z}_t)$",
        ha='center', va='center', fontsize=12, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')

ax.text(x4 + w4/2, y4 + h4 - 1.10, "Low-rank matrix:",
        ha='center', va='center', fontsize=10, color='#e8d0c0')
ax.text(x4 + w4/2, y4 + h4 - 1.40,
        r"$\mathbf{K} = \mathbf{U} \cdot \mathbf{V}^{\top} \quad (r=16)$",
        ha='center', va='center', fontsize=12, color=C_GOLD, fontweight='bold',
        family='serif', style='italic')

ax.text(x4 + w4/2, y4 + h4 - 1.80, "Multi-step propagation:",
        ha='center', va='center', fontsize=10, color='#e8d0c0')
ax.text(x4 + w4/2, y4 + h4 - 2.10,
        r"$\mathbf{z}_{t+n} = \mathbf{K}^n \mathbf{z}_t + \sum_{i=0}^{n-1} \mathbf{K}^i \mathbf{b}$",
        ha='center', va='center', fontsize=10, color='#e8d8c8',
        family='serif', style='italic')
ax.text(x4 + w4/2, y4 + h4 - 2.45, "Coherent modes: DMD spectral decomposition",
        ha='center', va='center', fontsize=8, color='#d0c0a0')

# Seta: Bloco 3 → Bloco 4
draw_arrow(ax, x3 + w3, y3 + h3*0.65, x4, y4 + h4*0.65)
draw_arrow_label(ax, (x3 + w3 + x4)/2, y3 + h3*0.65 + 0.15,
                 r"$\mathbf{g}(\mathbf{z}_t)$", fontsize=9)

# ------------------------------------------------------------------
# BLOCO 5 — PI-GNN (x=10.5, y=4.0)
# ------------------------------------------------------------------
x5, y5, w5, h5 = 10.5, 4.0, 3.8, 2.8
round_box(ax, x5, y5, w5, h5, C_GNN, alpha=0.92)
ax.text(x5 + w5/2, y5 + h5 - 0.25, "Physics-Informed GNN",
        ha='center', va='center', fontsize=14, color='white', fontweight='bold')

for i, txt in enumerate([
    "Spatial propagation on graph",
    "FireMessagePassing (3 layers)",
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

# Seta: Bloco 4 → Bloco 5
draw_arrow(ax, x4 + w4, y4 + h4*0.65, x5, y5 + h5*0.65)
draw_arrow_label(ax, (x4 + w4 + x5)/2, y4 + h4*0.65 + 0.20,
                 r"$\mathbf{z}_{t+1}$ (latent)", fontsize=8)

# ------------------------------------------------------------------
# BLOCO 6 — SAÍDA / PREVISÃO (x=10.5, y=8.0)
# ------------------------------------------------------------------
x7, y7, w7, h7 = 10.5, 7.2, 3.8, 1.8
round_box(ax, x7, y7, w7, h7, C_OUTPUT, alpha=0.92)
ax.text(x7 + w7/2, y7 + h7 - 0.30, "Prediction Output",
        ha='center', va='center', fontsize=13, color='white', fontweight='bold')
for i, txt in enumerate([
    "û(t+1) = predicted fire state",
    "FRP · Temperature · Spread rate",
    "Risk index · Coherent modes",
]):
    ax.text(x7 + w7/2, y7 + h7 - 0.65 - i*0.28, txt, ha='center', va='center',
            fontsize=9, color='#c0e0c8')

# Seta: Bloco 5 → Bloco 6 (através do decoder)
draw_arrow(ax, x5 + w5/2, y5 + h5, x7 + w7/2, y7, lw=2.0, color=C_GOLD,
           style='arc3,rad=0.12')

# Rótulo decoder
decoder_x = (x5 + w5/2 + x7 + w7/2)/2
decoder_y = (y5 + h5 + y7)/2 + 0.1
ax.plot(decoder_x, decoder_y, 'o', color=C_GOLD, markersize=6)
ax.text(decoder_x, decoder_y + 0.25, "Decoder: ẑ → x̂",
        ha='center', va='center', fontsize=8, color=C_GOLD)

# ------------------------------------------------------------------
# BLOCO 7 — FUNÇÃO DE PERDA (x=0.8, y=0.5)
# ------------------------------------------------------------------
x6, y6, w6, h6 = 0.8, 0.5, 11.2, 2.5
round_box(ax, x6, y6, w6, h6, '#EEF0F3', edgecolor='#999999', lw=1.0, alpha=0.4)

ax.text(x6 + 0.4, y6 + h6 - 0.35, "Total Loss Function",
        ha='left', va='center', fontsize=12, color=C_TEXT, fontweight='bold')

# Perdas individuais
loss_items = [
    (0.8,   y6 + h6 - 0.85, r"\mathcal{L}_{\text{recon}} = \|\mathbf{x}_t - \hat{\mathbf{x}}_t\|^2", "Reconstruction"),
    (0.8,   y6 + h6 - 1.30, r"\mathcal{L}_{\text{KL}} = -\frac{1}{2}\sum(1 + \log\sigma^2 - \mu^2 - \sigma^2)", "KL divergence"),
    (0.8,   y6 + h6 - 1.75, r"\mathcal{L}_{\text{pred}} = \|\mathbf{x}_{t+1} - \hat{\mathbf{x}}_{t+1}\|^2", "Prediction error"),
    (6.2,   y6 + h6 - 0.85, r"\mathcal{L}_{\text{GNN}} = \|\mathbf{z}^{\text{GNN}}_{t+1} - \mathbf{z}^{\text{Koop}}_{t+1}\|^2", "Latent consistency"),
    (6.2,   y6 + h6 - 1.30, r"\mathcal{L}_{\text{PDE}} = \|\frac{\partial u}{\partial t} - D\nabla^2 u - R(\theta, u, w)\|^2", "Physics (Rothermel)"),
    (6.2,   y6 + h6 - 1.75, r"\mathcal{L}_{bnd} = \mathrm{BC}(u|_{\partial\Omega}) + \mathrm{IC}(u|_{t=0})", "Boundary/Initial cond."),
]

for lx, ly, eq, label in loss_items:
    ax.text(lx + 5.6, ly + 0.08, f"${eq}$", ha='center', va='center',
            fontsize=9, color=C_TEXT, family='serif', style='italic')
    ax.text(lx + 5.6, ly - 0.20, f"— {label}", ha='center', va='center',
            fontsize=7, color=C_TEXT2)

# Equação total destacada
total_eq_x = 6.0
total_eq_y = y6 + 0.25
round_box(ax, total_eq_x - 1.5, total_eq_y, 5.0, 0.60, C_HIGHLIGHT,
          edgecolor=C_LOSS, lw=1.8, alpha=0.9)
ax.text(total_eq_x + 1.0, total_eq_y + 0.30,
        r"$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{recon}} + \beta\mathcal{L}_{\text{KL}} + \alpha\mathcal{L}_{\text{pred}} + \lambda_{\text{GNN}}\mathcal{L}_{\text{GNN}} + \lambda_{\text{PDE}}\mathcal{L}_{\text{PDE}}$",
        ha='center', va='center', fontsize=12, color=C_LOSS,
        fontweight='bold', family='serif')

# ------------------------------------------------------------------
# SETAS ADICIONAIS
# ------------------------------------------------------------------
# Bloco 2 → Bloco 6 (skip connection)
draw_arrow(ax, x2 + w2, y2 + h2*0.3, x7, y7 + h7*0.3,
           color='#aaaaaa', lw=1.2, style='arc3,rad=-0.3')
ax.text((x2 + w2 + x7)/2, (y2 + h2*0.3 + y7 + h7*0.3)/2 + 0.15,
        "Skip connection", ha='center', va='center', fontsize=7, color='#999999',
        style='italic')

# Loop de feedback: Loss → Koopman (backprop)
draw_arrow(ax, x6 + 2.5, y6 + h6, x4 + 0.5, y4, lw=1.5, color=C_LOSS,
           style='arc3,rad=0.25')
ax.text((x6 + 2.5 + x4 + 0.5)/2 - 0.6, (y6 + h6 + y4)/2 + 0.3,
        "Backprop (loss → K)", ha='center', va='center',
        fontsize=8, color=C_LOSS)

# ------------------------------------------------------------------
# EQUAÇÕES DE ROTHERMEL (canto direito)
# ------------------------------------------------------------------
roth_x = 15.2
roth_y = 7.5
roth_w = 2.5
roth_h = 1.5
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
        "Physics regularization", ha='center', va='center',
        fontsize=7, color=C_GOLD)

# ------------------------------------------------------------------
# LEGENDA
# ------------------------------------------------------------------
legend_elements = [
    mpatches.Patch(facecolor=C_SAT, edgecolor=C_BORDER, label='Satellite Data'),
    mpatches.Patch(facecolor=C_PREPROC, edgecolor=C_BORDER, label='Preprocessing'),
    mpatches.Patch(facecolor=C_VAE, edgecolor=C_BORDER, label='Variational Autoencoder'),
    mpatches.Patch(facecolor=C_KOOP, edgecolor=C_BORDER, label='Koopman Operator (K)'),
    mpatches.Patch(facecolor=C_GNN, edgecolor=C_BORDER, label='Physics-Informed GNN'),
    mpatches.Patch(facecolor=C_OUTPUT, edgecolor=C_BORDER, label='Prediction'),
    mpatches.Patch(facecolor=C_HIGHLIGHT, edgecolor=C_GOLD, label='Loss / Regularization'),
]

leg = ax.legend(
    handles=legend_elements,
    loc='lower center', fontsize=8, ncol=7,
    framealpha=0.85, facecolor=C_BG,
    edgecolor='#CCCCCC', labelcolor=C_TEXT,
    title='Components', title_fontsize=9,
    bbox_to_anchor=(0.5, 0.02),
)
leg.get_title().set_fontweight('bold')

# ------------------------------------------------------------------
# RODAPÉ
# ------------------------------------------------------------------
ax.text(FIG_W/2, 0.06,
    "Data flow: VIIRS/GOES → Preprocessing → VAE (Koopman observables) → K matrix → PI-GNN (Rothermel) → Decoder → Prediction",
    ha='center', va='center', fontsize=8, color='#999999', style='italic')

# ------------------------------------------------------------------
# SALVAR
# ------------------------------------------------------------------
out_figures = '/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/figures/diagrama-koopman-pignn.png'
out_artifacts = '/Users/naubergois/qclawmonitor/.stack/accounts/teams/gemeo-digital-queimadas/workspace/artifacts/diagrama-koopman-pignn.png'

plt.savefig(out_figures, dpi=300, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.savefig(out_artifacts, dpi=300, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.close()

print(f"✅ INOV-006: Diagrama de qualidade de publicação gerado")
print(f"   Figures: {out_figures}")
print(f"   Artifacts: {out_artifacts}")
print(f"   Tamanho (figures): {os.path.getsize(out_figures)/1024:.0f} KB")
print(f"   DPI: 300")
print(f"   Equações incluídas:")
print(f"     1. g(z_{{t+1}}) = K · g(z_t)")
print(f"     2. K = U · V^T (low-rank)")
print(f"     3. PDE residual: ∂u/∂t - D∇²u - R(θ,u,w)")
print(f"     4. Rothermel: R = R₀(1 + φ_w + φ_s)")
print(f"     5. L_total = L_recon + βL_KL + αL_pred + λ_GNN·L_GNN + λ_PDE·L_PDE")
