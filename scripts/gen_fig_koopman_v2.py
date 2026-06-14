#!/usr/bin/env python3
"""INOV-006: Figura Matematica — Diagrama Operador Koopman v2."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import os, datetime

DPI = 350
OUTDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/figures'
OUTDIR_K = OUTDIR + '/koopman'
os.makedirs(OUTDIR_K, exist_ok=True)

C_BG = '#1a1a2e'; C_BD = '#0f3460'; C_BP = '#16213e'; C_BA = '#1b2a4a'
C_G = '#f5c518'; C_GR = '#4ecca3'; C_B = '#4361ee'; C_P = '#7b2cbf'
C_T = '#ffffff'; C_T2 = '#b0b0b0'

fig, ax = plt.subplots(1, 1, figsize=(18, 11))
ax.set_xlim(0, 18); ax.set_ylim(0, 11); ax.axis('off')
fig.patch.set_facecolor(C_BG); ax.set_facecolor(C_BG)

fig.text(0.5, 0.97, "Figura 1 — Arquitetura NeKo-PIGNN: Neural Koopman Operator\nacoplado a Physics-Informed Graph Neural Network",
         ha='center', fontsize=16, fontweight='bold', color='white', transform=fig.transFigure)
fig.text(0.5, 0.945, "g(z\u209c\u208a\u2081) = K\u00b7g(z\u209c)  \u2022  \u2202u/\u2202t = D\u2207\u00b2u + R(\u03b8,w,u)  \u2022  L = L_data + \u03bb\u00b7L_PDE(Rothermel)",
         ha='center', fontsize=10, color=C_G, family='sans-serif', transform=fig.transFigure)

def dbox(ax, x, y, w, h, cl, title, lines, fst=13, fsl=8):
    ax.add_patch(FancyBboxPatch((x,y), w, h, boxstyle="round,pad=0.15", facecolor=cl, edgecolor='white', linewidth=1.5, alpha=0.9))
    ax.text(x+w/2, y+h-0.35, title, ha='center', va='top', fontsize=fst, fontweight='bold', color=C_T)
    for i, l in enumerate(lines):
        ax.text(x+w/2, y+h-0.75-i*0.30, l, ha='center', va='top', fontsize=fsl, color=C_T2, family='sans-serif')

def darr(ax, x1, y1, x2, y2, label='', cl='#8899aa', lw=2.0):
    ax.annotate('', xy=(x2,y2), xytext=(x1,y1),
                arrowprops=dict(arrowstyle='->', color=cl, lw=lw, connectionstyle='arc3,rad=0.10'))
    if label:
        ax.text((x1+x2)/2+0.15, (y1+y2)/2+0.25, label, fontsize=8, color=cl, fontstyle='italic',
                ha='center', va='bottom', bbox=dict(boxstyle='round,pad=0.08', facecolor=C_BG, edgecolor='none', alpha=0.8))

dbox(ax, 0.3, 5.5, 2.8, 1.8, C_BD, "\u2460 Dados de Sat\u00e9lite",
     ["VIIRS S-NPP/NOAA-20 (375m)", "GOES-16 ABI CH02/05/07 (2km)",
      "INPE BDQueimadas + NASA FIRMS", "2024\u20132026 | Cear\u00e1, Brasil"])
darr(ax, 3.1, 6.8, 4.6, 6.8, "fus\u00e3o espacial")

dbox(ax, 4.6, 5.8, 2.5, 1.6, C_BP, "\u2461 Pr\u00e9-processamento",
     ["Normaliza\u00e7\u00e3o Z-score", "K-Means (k=8) + DQF",
      "Fus\u00e3o GOES+VIIRS (375m)", "Grid 2D \u2192 Grafo G(V,E)"])
darr(ax, 7.1, 6.8, 8.5, 6.8, "x\u2208\u211D\u207f \u2192 z\u2208\u211D\u1d50", cl=C_G)

dbox(ax, 8.5, 3.8, 3.0, 4.5, C_BA, "\u2462 Autoencoder Variacional",
     ["x \u2192 EncoderMLP(x) \u2192 \u03bc, log \u03c3",
      "z = \u03bc + \u03c3\u2299\u03b5, \u03b5\u223cN(0,I)",
      "DecoderMLP(z) \u2192 x\u0302",
      "Observ\u00e1veis Koopman: g(z)={z, z\u00b2, sin, cos}",
      "Latent dim: d = 32",
      "\u2112_VAE = \u2112_recon + \u03b2\u00b7\u2112_KL"])
lat = FancyBboxPatch((9.2, 4.5), 1.6, 0.55, boxstyle="round,pad=0.08",
                      facecolor=C_B, edgecolor=C_G, linewidth=2.5, alpha=0.85)
ax.add_patch(lat)
ax.text(10.0, 4.77, "z\u209c \u2208 \u211D\u1d50", ha='center', va='center',
        fontsize=12, fontweight='bold', color='white')

darr(ax, 11.5, 6.8, 13.0, 7.8, "g(z\u209c) \u2192 K", cl=C_G, lw=2.2)

dbox(ax, 13.0, 6.5, 3.5, 2.0, C_G, "\u2463 Operador de Koopman (K)",
     ["g(z\u209c\u208a\u2081) = K \u00b7 g(z\u209c)", "K \u2208 \u211D\u1d50\u02e3\u1d50, m=dim(g)",
      "K \u2248 U\u2096\u03a3\u2096V\u2096\u1d40 (SVD low-rank)",
      "Propaga\u00e7\u00e3o: g(z\u209c\u208a\u2096) = K\u1d56\u00b7g(z\u209c)",
      "Modos Coerentes: \u03a6 = \u03a8\u00b7V\u2096"])
darr(ax, 14.75, 6.5, 14.75, 4.5, "z\u0302\u209c\u208a\u2081 = dec(g(z\u209c\u208a\u2081))", cl=C_GR)
darr(ax, 11.5, 3.8, 13.0, 3.8, "skip z\u209c", cl=C_B, lw=1.5)

dbox(ax, 13.0, 2.2, 3.5, 2.6, C_GR, "\u2464 PI-GNN (Physics-Informed)",
     ["FireMessagePassing Layer \u00d74",
      "Aten\u00e7\u00e3o direcional (vento):",
      "  \u03b1\u1d62\u2c7c = softmax(q\u1d62\u00b7k\u2c7c + w_dir\u00b7\u00ea\u1d62\u2c7c)",
      "Encoder \u2192 MP(4) \u2192 Decoder",
      "Skip connections residuais",
      "Sa\u00edda: u\u0302\u209c\u208a\u2081 (risco)"])
darr(ax, 14.75, 2.2, 14.75, 1.0, "u\u0302, \u0177", cl=C_P)

dbox(ax, 13.0, 0.1, 3.5, 1.3, C_P, "\u2465 Fun\u00e7\u00e3o de Perda Total L",
     ["L = L_recon + L_pred + L_GNN + L_PDE",
      "L_PDE = ||\u2202u/\u2202t - D\u2207\u00b2u - R(\u03b8,w,u)||\u00b2"])

bg = FancyBboxPatch((12.5, 0.0), 4.5, 8.8, boxstyle="round,pad=0.1",
                     facecolor=C_G, edgecolor='none', alpha=0.06)
ax.add_patch(bg)
ax.text(17.15, 4.4, "NEKO-PIGNN\nMODELO\nH\u00cdBRIDO", ha='center', va='center',
        fontsize=10, fontweight='bold', color=C_G, linespacing=1.4)

plt.legend(handles=[
    mpatches.Patch(facecolor=C_BD, edgecolor='white', label='\u2460 Dados entrada'),
    mpatches.Patch(facecolor=C_BP, edgecolor='white', label='\u2461 Pr\u00e9-processamento'),
    mpatches.Patch(facecolor=C_BA, edgecolor='white', label='\u2462 Autoencoder VAE'),
    mpatches.Patch(facecolor=C_G, edgecolor='white', label='\u2463 Operador Koopman'),
    mpatches.Patch(facecolor=C_GR, edgecolor='white', label='\u2464 PI-GNN / Rothermel'),
    mpatches.Patch(facecolor=C_P, edgecolor='white', label='\u2465 Fun\u00e7\u00e3o Perda'),
], loc='lower left', fontsize=9, framealpha=0.85, facecolor='#0d0d1a',
   edgecolor='white', labelcolor='white', title='Componentes', title_fontsize=10)

fig.text(0.5, 0.02,
         "VIIRS/GOES-16 \u2192 Autoencoder \u2192 Espa\u00e7o Koopman (lineariza\u00e7\u00e3o) \u2192 PI-GNN (Rothermel PDE) \u2192 Previs\u00e3o + Perda F\u00edsica",
         ha='center', fontsize=8, color='#666666', fontstyle='italic', transform=fig.transFigure)

png_p = OUTDIR + '/diagrama-koopman-pignn.png'
svg_p = OUTDIR_K + '/diagrama-koopman-pignn.svg'
plt.savefig(png_p, dpi=DPI, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.savefig(svg_p, dpi=DPI, bbox_inches='tight', facecolor=C_BG, edgecolor='none', format='svg')
print(f"PNG: {png_p}")
print(f"SVG: {svg_p}")
print(f"Sizes: {os.path.getsize(png_p)//1024} KB, {os.path.getsize(svg_p)//1024} KB")
plt.close()
print("Done:", datetime.datetime.now().isoformat())
