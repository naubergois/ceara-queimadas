#!/usr/bin/env bash
# TASK-014: GitHub release + optional Zenodo deposition (requires ZENODO_ACCESS_TOKEN).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TAG="${1:-v1.0.0-ems-submission}"
ZENODO_API="${ZENODO_API:-https://zenodo.org/api}"
BUNDLE_ZIP="${ROOT}/submission/zenodo_bundle_${TAG}.zip"
EMS_ZIP="${ROOT}/submission/EMS_SUBMISSION_PACKAGE.zip"

echo "==> 1/4 Refresh bundles"
./scripts/prepare_zenodo_release.sh "$TAG"
./scripts/build_ems_submission_package.sh

echo "==> 2/4 GitHub release ${TAG}"
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release ${TAG} already exists — uploading assets if missing"
  gh release upload "$TAG" "$BUNDLE_ZIP" "$EMS_ZIP" --clobber 2>/dev/null || true
else
  gh release create "$TAG" \
    --title "EMS submission reproducibility (${TAG})" \
    --notes "$(cat <<EOF
Reproducibility archive for *Environmental Modelling & Software* submission.

- \`EMS_SUBMISSION_PACKAGE.zip\` — full Editorial Manager upload bundle
- \`zenodo_bundle_${TAG}.zip\` — Zenodo deposition archive

GitHub: https://github.com/naubergois/ceara-queimadas
Manuscript: artigo-queimadas-gemeo-digital-en.pdf (49 pages)
EOF
)" \
    "$BUNDLE_ZIP" "$EMS_ZIP"
fi
RELEASE_URL="https://github.com/naubergois/ceara-queimadas/releases/tag/${TAG}"
echo "GitHub release: ${RELEASE_URL}"

echo "==> 3/4 Zenodo deposition (optional)"
if [[ -z "${ZENODO_ACCESS_TOKEN:-}" ]]; then
  echo "ZENODO_ACCESS_TOKEN not set — skip API upload."
  echo "Manual: upload ${BUNDLE_ZIP} at https://zenodo.org/deposit/new"
  echo "         (metadata in submission/.zenodo.json)"
  exit 0
fi

DEP=$(curl -sS -X POST "${ZENODO_API}/deposit/depositions" \
  -H "Authorization: Bearer ${ZENODO_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @"${ROOT}/submission/.zenodo.json")
DEP_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"$DEP")
BUCKET=$(python3 -c "import json,sys; print(json.load(sys.stdin)['links']['bucket'])" <<<"$DEP")
FILENAME=$(basename "$BUNDLE_ZIP")

curl -sS -X PUT "${BUCKET}/${FILENAME}?access_token=${ZENODO_ACCESS_TOKEN}" \
  --upload-file "$BUNDLE_ZIP" \
  -H "Content-Type: application/zip"

PUBLISHED=$(curl -sS -X POST "${ZENODO_API}/deposit/depositions/${DEP_ID}/actions/publish" \
  -H "Authorization: Bearer ${ZENODO_ACCESS_TOKEN}")
DOI=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('doi',''))" <<<"$PUBLISHED")
echo "Zenodo DOI: ${DOI}"
echo "${DOI}" > "${ROOT}/submission/ZENODO_DOI.txt"

echo "==> 4/4 Update manuscript Data Availability (if DOI obtained)"
if [[ -n "$DOI" && "$DOI" != "None" ]]; then
  python3 <<PY
from pathlib import Path
tex = Path("${ROOT}/artigo-queimadas-gemeo-digital-en.tex")
text = tex.read_text()
needle = "Zenodo bundle: \\\\path{scripts/prepare_zenodo_release.sh}"
replacement = f"Reproducibility archive: \\\\url{{https://doi.org/${DOI.replace('https://doi.org/','')}}} (GitHub release: \\\\url{${RELEASE_URL}}})"
if needle in text:
    tex.write_text(text.replace(needle, replacement))
    print("Updated artigo-queimadas-gemeo-digital-en.tex with Zenodo DOI")
PY
fi
