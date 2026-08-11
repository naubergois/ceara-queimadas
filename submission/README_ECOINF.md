# Ecological Informatics — Submission Package

Journal: **Ecological Informatics** (Elsevier, full OA)  
Portal: https://submit.elsevier.com/ECOINF  
Guide: https://www.sciencedirect.com/journal/ecological-informatics/publish/guide-for-authors  
APC: ~USD 3,190 (excluding taxes; check current GPOA/institutional waivers)

## Manuscript files

| File | Purpose |
|------|---------|
| `../artigo-queimadas-gemeo-digital-en.tex` | Main LaTeX source (`elsarticle`) |
| `../artigo-queimadas-gemeo-digital-en.pdf` | Compiled PDF for upload |
| `refs-ems.bib` | BibTeX database (consistent style) |
| `highlights.txt` | Highlights (upload separately) |
| `cover_letter.pdf` | Cover letter |
| `graphical_abstract.png` | Graphical abstract |
| `supplementary.pdf` | Supplementary Information |
| `ECOINF_SUBMISSION_PACKAGE/` | Assembled upload folder |
| `checklist_ecoinf.md` | Internal checklist |

## Elsevier format applied

- `\documentclass[preprint,12pt,times,numbers]{elsarticle}`
- `\journal{Ecological Informatics}`
- Frontmatter: abstract (≤250 words), keywords (1–7), highlights file
- Target length: ≤7,000 words preferred (max 10,000)
- Backmatter: CRediT, Data/Code Availability, competing interest, generative AI declaration
- References: `\bibliographystyle{elsarticle-num}` + `\bibliography{submission/refs-ems}`

## Compile and package

```bash
./scripts/compile_ems_submission.sh
./scripts/build_ecoinf_submission_package.sh
```

## Editorial Manager upload

1. **Manuscript PDF** — `01_Manuscript.pdf`
2. **LaTeX source** — `02_LaTeX_Source.zip`
3. **Highlights** — `04_Highlights.txt`
4. **Cover letter** — `03_Cover_Letter.pdf`
5. **Graphical abstract** — `05_Graphical_Abstract.png`
6. **Supplementary** — `06_Supplementary_Information.pdf`
7. Register **ORCID** for all five authors
