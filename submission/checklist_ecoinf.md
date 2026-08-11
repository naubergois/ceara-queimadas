# Checklist de Submissão — Ecological Informatics

**Manuscrito:** `artigo-queimadas-gemeo-digital-en.tex`  
**Pacote:** `submission/ECOINF_SUBMISSION_PACKAGE/`

## Pré-requisitos Elsevier / EI

- [x] Template `elsarticle` (preprint)
- [x] `\journal{Ecological Informatics}`
- [x] Argumento ecológico (Caatinga, biodiversidade, gestão)
- [x] Abstract EN ≤250 palavras · Keywords (7) · Highlights
- [x] Cover letter ECOINF (fit + menção transferência pós-EMS)
- [x] Graphical abstract · Supplementary SI
- [x] BibTeX `submission/refs-ems.bib`
- [x] Contagem de palavras do PDF ≤10 000 (≈9 724 no build; meta ≤7–8 000 corpo)
- [ ] Zenodo DOI (opcional; ver `ZENODO.md`)

## Editorial Manager

Portal: https://submit.elsevier.com/ECOINF · Tipo: **Research Article** · OA APC ~USD 3 190

| # | Arquivo | Campo EM |
|---|---------|----------|
| 1 | `01_Manuscript.pdf` | Manuscript |
| 2 | `02_LaTeX_Source.zip` | LaTeX source |
| 3 | `03_Cover_Letter.pdf` | Cover letter |
| 4 | `04_Highlights.txt` | Highlights |
| 5 | `05_Graphical_Abstract.png` | Graphical abstract |
| 6 | `06_Supplementary_Information.pdf` | Supplementary |

Antes de **Submit**:
- [ ] ORCID dos 5 autores no EM
- [ ] Revisores sugeridos (cover letter)
- [ ] Confirmar APC / waiver institucional se aplicável

Regenerar pacote: `./scripts/build_ecoinf_submission_package.sh`
