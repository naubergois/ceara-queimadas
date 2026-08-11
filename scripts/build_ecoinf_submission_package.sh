#!/usr/bin/env bash
# Build Ecological Informatics submission package for Editorial Manager.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PKG_DIR="${ROOT}/submission/ECOINF_SUBMISSION_PACKAGE"
PKG_ZIP="${ROOT}/submission/ECOINF_SUBMISSION_PACKAGE.zip"
TAG="v1.0.0-ems-submission"

echo "==> 1/5 Compile manuscript"
./scripts/compile_ems_submission.sh

echo "==> 2/5 Compile supplementary"
pdflatex -interaction=nonstopmode -output-directory=submission submission/supplementary.tex >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode -output-directory=submission submission/supplementary.tex >/dev/null 2>&1 || true

echo "==> 3/5 Compile cover letter"
pdflatex -interaction=nonstopmode -output-directory=submission submission/cover_letter.tex >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode -output-directory=submission submission/cover_letter.tex >/dev/null 2>&1 || true

echo "==> 4/5 LaTeX source zip"
./scripts/package_ems_upload.sh

echo "==> 5/5 Assemble ECOINF_SUBMISSION_PACKAGE/"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"

cp artigo-queimadas-gemeo-digital-en.pdf submission/manuscript.pdf
cp submission/manuscript.pdf "$PKG_DIR/01_Manuscript.pdf"
cp submission/latex_source.zip "$PKG_DIR/02_LaTeX_Source.zip"
cp submission/cover_letter.pdf "$PKG_DIR/03_Cover_Letter.pdf"
cp submission/highlights.txt "$PKG_DIR/04_Highlights.txt"
cp submission/graphical_abstract.png "$PKG_DIR/05_Graphical_Abstract.png"
cp submission/supplementary.pdf "$PKG_DIR/06_Supplementary_Information.pdf"
cp submission/ORCID_AUTHORS.md "$PKG_DIR/ORCID_AUTHORS.md"
cp submission/ZENODO.md "$PKG_DIR/ZENODO.md"
cp submission/README_ECOINF.md "$PKG_DIR/README_ECOINF.md"
cp submission/checklist_ecoinf.md "$PKG_DIR/checklist_ecoinf.md"
if [[ -f "submission/zenodo_bundle_${TAG}.zip" ]]; then
  cp "submission/zenodo_bundle_${TAG}.zip" "$PKG_DIR/07_Zenodo_Reproducibility_Bundle.zip"
elif [[ -f scripts/prepare_zenodo_release.sh ]]; then
  ./scripts/prepare_zenodo_release.sh "$TAG" 2>/dev/null || true
  [[ -f "submission/zenodo_bundle_${TAG}.zip" ]] && \
    cp "submission/zenodo_bundle_${TAG}.zip" "$PKG_DIR/07_Zenodo_Reproducibility_Bundle.zip" || true
fi

python3 << 'PY'
import json, re
from datetime import date
from pathlib import Path

root = Path(".")
tex = (root / "artigo-queimadas-gemeo-digital-en.tex").read_text()
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S).group(1)
plain = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", abstract)
plain = re.sub(r"\\[a-zA-Z]+|[$~{}]", " ", plain)
plain = re.sub(r"\s+", " ", plain).strip()
keywords = [
    k.strip()
    for k in re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", tex, re.S)
    .group(1)
    .replace("\\sep", "|")
    .split("|")
    if k.strip()
]
highlights = [
    ln.strip()
    for ln in (root / "submission/highlights.txt").read_text().splitlines()
    if ln.strip()
]

pdf_words = None
pdf = root / "artigo-queimadas-gemeo-digital-en.pdf"
try:
    import subprocess
    out = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True, errors="ignore")
    pdf_words = len(out.split())
except Exception:
    pass

manifest = {
    "journal": "Ecological Informatics (Elsevier)",
    "portal": "https://submit.elsevier.com/ECOINF",
    "article_type": "Research Article",
    "title": "Ceará Wildfire Digital Twin: An Open-Source Agentic AI Platform with LangGraph",
    "date_built": str(date.today()),
    "abstract_words": len(plain.split()),
    "pdf_words_approx": pdf_words,
    "keywords_count": len(keywords),
    "keywords": keywords,
    "highlights": highlights,
    "files": [
        {"name": "01_Manuscript.pdf", "role": "Main manuscript PDF"},
        {"name": "02_LaTeX_Source.zip", "role": "LaTeX source + figures + BibTeX"},
        {"name": "03_Cover_Letter.pdf", "role": "Cover letter to editor"},
        {"name": "04_Highlights.txt", "role": "Highlights (3-5 bullets, upload separately)"},
        {"name": "05_Graphical_Abstract.png", "role": "Graphical abstract"},
        {"name": "06_Supplementary_Information.pdf", "role": "Supplementary material"},
        {"name": "07_Zenodo_Reproducibility_Bundle.zip", "role": "Optional: upload to Zenodo for DOI"},
        {"name": "ORCID_AUTHORS.md", "role": "Register ORCID in Editorial Manager"},
        {"name": "ZENODO.md", "role": "Zenodo DOI instructions"},
        {"name": "README_SUBMISSION.txt", "role": "Upload guide"},
    ],
    "github": "https://github.com/naubergois/ceara-queimadas",
    "pending_manual": [
        "Register ORCID for all 5 authors in Editorial Manager",
        "Confirm APC / institutional OA waiver if applicable",
        "Upload files 01-06 to Editorial Manager (ECOINF)",
        "Suggest reviewers listed in cover letter",
    ],
}
out = root / "submission/ECOINF_SUBMISSION_PACKAGE/MANIFEST.json"
out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(
    f"Manifest: abstract={manifest['abstract_words']} words, "
    f"pdf≈{pdf_words} words, keywords={manifest['keywords_count']}"
)
PY

cat > "$PKG_DIR/README_SUBMISSION.txt" << 'EOF'
ECOINF SUBMISSION PACKAGE — Ecological Informatics
==================================================

Portal: https://submit.elsevier.com/ECOINF
Article type: Research Article (full open access)

UPLOAD TO EDITORIAL MANAGER (in this order)
-------------------------------------------
1. 01_Manuscript.pdf              → Main manuscript
2. 02_LaTeX_Source.zip           → LaTeX source files
3. 03_Cover_Letter.pdf           → Cover letter
4. 04_Highlights.txt             → Highlights (separate field/file)
5. 05_Graphical_Abstract.png     → Graphical abstract
6. 06_Supplementary_Information.pdf → Supplementary material

BEFORE SUBMITTING
-----------------
- Register ORCID for all authors (see ORCID_AUTHORS.md)
- Confirm APC / waiver (journal is full OA)
- Optional: Zenodo DOI from 07_Zenodo_Reproducibility_Bundle.zip
- Suggested reviewers are listed in the cover letter

GITHUB
------
https://github.com/naubergois/ceara-queimadas
EOF

rm -f "$PKG_ZIP"
(cd submission && zip -rq ECOINF_SUBMISSION_PACKAGE.zip ECOINF_SUBMISSION_PACKAGE)

echo ""
echo "=== Ecological Informatics Submission Package Ready ==="
ls -lh "$PKG_ZIP"
echo ""
echo "Contents:"
ls -lh "$PKG_DIR"
