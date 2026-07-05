# Zenodo release checklist (EMS submission) — TASK-014

## Automated (recommended)

```bash
chmod +x scripts/publish_zenodo_deposit.sh
./scripts/publish_zenodo_deposit.sh v1.0.0-ems-submission
```

This script:
1. Refreshes `zenodo_bundle_v1.0.0-ems-submission.zip` and `EMS_SUBMISSION_PACKAGE.zip`
2. Creates GitHub release `v1.0.0-ems-submission` with both zips as assets
3. If `ZENODO_ACCESS_TOKEN` is set, publishes to Zenodo and writes `submission/ZENODO_DOI.txt`

Get a Zenodo token: https://zenodo.org/account/settings/applications/tokens/new  
Scopes: `deposit:write`, `deposit:actions`

```bash
export ZENODO_ACCESS_TOKEN='your-token'
./scripts/publish_zenodo_deposit.sh
```

## Manual upload (no token)

1. Open https://zenodo.org/deposit/new
2. Upload `submission/zenodo_bundle_v1.0.0-ems-submission.zip`
3. Import metadata from `submission/.zenodo.json` (or copy fields from `ZENODO_METADATA.txt`)
4. Publish and copy DOI into `artigo-queimadas-gemeo-digital-en.tex` §Data Availability

## Metadata

| Field | Value |
|-------|-------|
| Title | Ceará Wildfire Digital Twin — reproducibility archive (EMS submission) |
| License | CC-BY-4.0 (archive) + MIT (code in GitHub) |
| Keywords | wildfire, digital twin, LangGraph, INPE, FIRMS, NeKo-PIGNN |
| GitHub | https://github.com/naubergois/ceara-queimadas |
| Release | https://github.com/naubergois/ceara-queimadas/releases/tag/v1.0.0-ems-submission |

## Citation (after DOI)

`Gois, N., et al. (2026). Ceará Wildfire Digital Twin — reproducibility archive. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX`

Until Zenodo DOI is minted, EMS accepts the **GitHub release tag** plus `scripts/reproduce_inpe_data.sh` (see Elsevier data-availability policy).
