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
# Experiment input data (all datasets used by the manuscript experiments)
cp data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv "$OUT/data/" 2>/dev/null || true
cp backend/experiments/data/climate_ceara_90d.json "$OUT/data/" 2>/dev/null || true
cp backend/experiments/data/firms_ceara_7d.json "$OUT/data/" 2>/dev/null || true
cp backend/experiments/data/inpe_ceara_historico.json "$OUT/data/" 2>/dev/null || true
cp backend/experiments/data/inpe_monthly_br/focos_ma_dry_2025.csv "$OUT/data/" 2>/dev/null || true
cp backend/experiments/data/inpe_monthly_br/focos_pi_dry_2025.csv "$OUT/data/" 2>/dev/null || true
cat > "$OUT/data/README.txt" <<'DATA'
Datasets used by the manuscript experiments
-------------------------------------------
focos_ce_INPE_2024_2026.csv   INPE BDQueimadas hotspots, Ceara, 2024-2026 (main validation)
climate_ceara_90d.json        Open-Meteo daily climate, 15 municipalities, 90+ days
firms_ceara_7d.json           NASA FIRMS active fires snapshot (7 days)
inpe_ceara_historico.json     INPE historical hotspot archive (JSON)
focos_ma_dry_2025.csv         INPE hotspots, Maranhao dry season 2025 (external-state validation)
focos_pi_dry_2025.csv         INPE hotspots, Piaui dry season 2025 (external-state validation)

Brazil-wide raw monthly INPE files (focos_mensal_br_YYYYMM.csv, ~580 MB) are
not bundled; regenerate them with scripts/reproduce_inpe_data.sh, which
downloads directly from the INPE open data portal.
DATA
cp scripts/reproduce_inpe_data.sh scripts/prepare_zenodo_release.sh scripts/publish_zenodo_deposit.sh "$OUT/scripts/" 2>/dev/null || true
cp submission/.zenodo.json "$OUT/.zenodo.json" 2>/dev/null || true

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
