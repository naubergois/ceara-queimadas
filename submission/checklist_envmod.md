# Checklist de Submissão — Environmental Modelling & Software

**Manuscrito:** `artigo-queimadas-gemeo-digital-en.tex`  
**Pacote:** `submission/EMS_SUBMISSION_PACKAGE.zip` (~15 MB)

## Pré-requisitos Elsevier

- [x] Template `elsarticle.cls` (preprint)
- [x] Título, 5 autores, CRediT, emails, ORCID no PDF
- [x] Abstract EN (123 palavras) · Keywords (7) · Highlights
- [x] Cover letter · Graphical abstract · Supplementary SI
- [x] BibTeX `submission/refs-ems.bib`
- [x] GitHub release `v1.0.0-ems-submission` (reproducibility)
- [ ] Zenodo DOI (opcional pós-release; ver `ZENODO.md` + `ZENODO_ACCESS_TOKEN`)

## Evidência científica (EMS-10)

- [x] EXP-ROBUST-001 … 006 · scripts INPE · SI · ReAct+RAG figura

## Submissão Editorial Manager — TASK-029

Portal: https://www.editorialmanager.com/envsoft/ · Tipo: **Research Article**

| # | Arquivo local | Campo EM |
|---|---------------|----------|
| 1 | `EMS_SUBMISSION_PACKAGE/01_Manuscript.pdf` | Manuscript |
| 2 | `EMS_SUBMISSION_PACKAGE/02_LaTeX_Source.zip` | LaTeX source |
| 3 | `EMS_SUBMISSION_PACKAGE/03_Cover_Letter.pdf` | Cover letter |
| 4 | `EMS_SUBMISSION_PACKAGE/04_Highlights.txt` | Highlights |
| 5 | `EMS_SUBMISSION_PACKAGE/05_Graphical_Abstract.png` | Graphical abstract |
| 6 | `EMS_SUBMISSION_PACKAGE/06_Supplementary_Information.pdf` | Supplementary |

Antes de clicar **Submit**:
- [ ] Confirmar ORCID dos 5 autores no EM (`ORCID_AUTHORS.md`)
- [ ] Revisores sugeridos (cover letter §3): Brunton, Karniadakis, Ager
- [ ] (Opcional) Anexar DOI Zenodo em Data Availability após mint

## Cards Kanban EMS-10

| ID | Status |
|----|--------|
| TASK-014 | done (GitHub release + bundle; Zenodo API se token) |
| TASK-017 … TASK-037 | done |
| TASK-029 | done (pacote pronto; falta upload manual no EM) |

Regenerar pacote: `./scripts/build_ems_submission_package.sh`
