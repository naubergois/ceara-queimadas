# Environmental Modelling & Software — Submission Package

Journal: **Environmental Modelling & Software** (Elsevier)  
Portal: https://www.editorialmanager.com/envsoft/

## Manuscript files

| File | Purpose |
|------|---------|
| `../artigo-queimadas-gemeo-digital-en.tex` | Main LaTeX source (elsarticle) |
| `../artigo-queimadas-gemeo-digital-en.pdf` | Compiled PDF for upload |
| `refs-ems.bib` | BibTeX database (83 entries) |
| `highlights.txt` | Highlights (upload separately) |
| `cover_letter.pdf` | Cover letter |
| `graphical_abstract.png` | Graphical abstract (1328×531, EMS minimum) |
| `graphical_abstract_2k.png` | Full 2K source (2816×1584) |
| `manuscript.pdf` | Compiled PDF for upload (copy of main PDF) |
| `supplementary.pdf` | Supplementary Information |
| `latex_source.zip` | LaTeX source bundle for EM (`scripts/package_ems_upload.sh`) |
| `scripts/publish_zenodo_deposit.sh` | GitHub release + optional Zenodo DOI (TASK-014) |
| `zenodo_bundle_v1.0.0-ems-submission.zip` | Reproducibility archive for Zenodo |
| `SUBMISSION_UPLOAD.md` | Final upload checklist |
| `ORCID_AUTHORS.md` | ORCID registration guide |
| `checklist_envmod.md` | Internal checklist |
| `ZENODO.md` | DOI release instructions |

## Elsevier format applied

- `\documentclass[preprint,12pt,times,numbers]{elsarticle}`
- `\journal{Environmental Modelling \& Software}`
- Frontmatter: abstract, keywords (`\begin{keyword}...\sep...\end{keyword}`)
- Backmatter: CRediT, Data/Code Availability, competing interest, generative AI declaration
- References: `\bibliographystyle{elsarticle-num}` + `\bibliography{submission/refs-ems}`

## Compile

```bash
./scripts/compile_ems_submission.sh
```

Or manually: `pdflatex` → `bibtex` → `pdflatex` × 2.

## Editorial Manager upload

1. **Manuscript PDF** — `artigo-queimadas-gemeo-digital-en.pdf`
2. **LaTeX source** — zip containing `.tex`, `refs-ems.bib`, `figures/`, `backend/experiments/results/*.tex`
3. **Highlights** — `highlights.txt`
4. **Cover letter** — `cover_letter.pdf`
5. Register **ORCID** for all five authors in the system

## Regenerate bibliography from inline refs (if restoring thebibliography)

```bash
python3 scripts/tex_bibitems_to_bib.py
python3 scripts/normalize_refs_ems_bib.py
```
