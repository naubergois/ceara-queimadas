#!/usr/bin/env bash
# Prepare Zenodo/GitHub release bundle (TASK-014). Run after final PDF compile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TAG="${1:-v1.0.0-ems-submission}"
OUT="${ROOT}/submission/zenodo_bundle"
rm -rf "$OUT"
mkdir -p "$OUT"/{article,experiments,data,scripts}

cp artigo-queimadas-gemeo-digital-en.tex artigo-queimadas-gemeo-digital-en.pdf "$OUT/article/" 2>/dev/null || true
cp submission/cover_letter.pdf submission/highlights.txt submission/refs-ems.bib "$OUT/article/"
cp -r backend/experiments/results/*.json backend/experiments/results/*.md "$OUT/experiments/" 2>/dev/null || true
cp backend/experiments/results/tabela_*.tex "$OUT/experiments/" 2>/dev/null || true
cp data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv "$OUT/data/" 2>/dev/null || true
cp scripts/reproduce_inpe_data.sh scripts/prepare_zenodo_release.sh "$OUT/scripts/"

cat > "$OUT/ZENODO_METADATA.txt" <<EOF
Title: Ceará Wildfire Digital Twin — reproducibility archive
Version: ${TAG}
License: MIT (code) + CC-BY-4.0 (article PDF)
Keywords: wildfire, digital twin, LangGraph, INPE, FIRMS, NeKo-PIGNN
Upload: https://zenodo.org/deposit/new
GitHub release: ${TAG}
EOF

(cd "$OUT" && zip -rq "${ROOT}/submission/zenodo_bundle_${TAG}.zip" .)
echo "Bundle: submission/zenodo_bundle_${TAG}.zip"
echo "Next: create GitHub release ${TAG}, enable Zenodo-GitHub integration, upload zip."
