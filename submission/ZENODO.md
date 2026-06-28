# Zenodo release checklist (EMS submission)

1. Create GitHub release `v1.0.0-ems-submission` from commit hash used for submission.
2. Upload to Zenodo (link GitHub repo or upload zip):
   - `artigo-queimadas-gemeo-digital-en.tex` + PDF
   - `backend/experiments/results/` (all EXP-ROBUST JSON + `.tex` tables)
   - `data/inpe_focos_ce/` CSVs (or `scripts/reproduce_inpe_data.sh` only if size limits apply)
3. Metadata:
   - Title: *Ceará Digital Twin for Wildfires — reproducibility archive*
   - Authors: same as manuscript
   - License: MIT (code) + CC-BY-4.0 (article PDF)
   - Keywords: wildfire, digital twin, LangGraph, INPE, FIRMS
4. Copy DOI into `artigo-queimadas-gemeo-digital-en.tex` §Data Availability.
5. Cite as: `Gois, N., et al. (2026). Ceará Wildfire Digital Twin reproducibility archive. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX`

Until DOI is minted, the GitHub tag above satisfies EMS data-availability review when combined with `scripts/reproduce_inpe_data.sh`.
