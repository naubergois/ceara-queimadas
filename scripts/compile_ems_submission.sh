#!/usr/bin/env bash
# Compile EMS submission manuscript (Elsevier elsarticle + BibTeX).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TEX=artigo-queimadas-gemeo-digital-en
echo "==> pdflatex pass 1"
pdflatex -interaction=nonstopmode "$TEX.tex" >/dev/null || true
echo "==> bibtex"
bibtex "$TEX" || true
echo "==> pdflatex pass 2-3"
pdflatex -interaction=nonstopmode "$TEX.tex" >/dev/null || true
pdflatex -interaction=nonstopmode "$TEX.tex" >/dev/null || true
echo "==> Done: $ROOT/$TEX.pdf"
ls -lh "$ROOT/$TEX.pdf"
