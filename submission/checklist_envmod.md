# Checklist de Submissão — Environmental Modelling & Software

**Manuscrito:** `artigo-queimadas-gemeo-digital-en.tex`  
**Nota estimada:** ~9.4–9.6 / 10 (pós EMS-10 parcial)

## Pré-requisitos Elsevier

- [x] Template `elsarticle.cls` (preprint)
- [x] Título atual: *Ceará Digital Twin for Wildfires…*
- [x] 5 autores + CRediT + emails
- [x] Abstract EN (150–250 palavras)
- [x] Highlights (`submission/highlights.txt`, ≤85 chars)
- [x] Keywords
- [x] Cover letter atualizada (`submission/cover_letter.pdf`)
- [ ] ORCID reais de todos os autores (registrar no Editorial Manager)
- [ ] BibTeX externo (`docs/refs-queimadas.bib`) — ainda inline no `.tex`
- [ ] Zenodo DOI (`submission/ZENODO.md` — pendente release)

## Evidência científica (EMS-10)

- [x] EXP-ROBUST-001 bootstrap CI
- [x] EXP-ROBUST-002 GOES pixel
- [x] EXP-ROBUST-003 temporal + LOO sazonal
- [x] EXP-ROBUST-004 RAG Recall@5 = 98% (glossary bilíngue)
- [x] Script INPE `scripts/reproduce_inpe_data.sh`
- [ ] NeKo ≥12 meses ou reframing (TASK-023)
- [ ] Validação externa MA/PI (TASK-022)
- [ ] Copyedit nativo (TASK-018)

## Submissão Editorial Manager

1. [ ] Compilar PDF final (`pdflatex` 2×)
2. [ ] Anexar: Manuscript PDF, Cover Letter, Highlights
3. [ ] Sugerir 3 revisores (ver cover letter)
4. [ ] Submeter: https://www.editorialmanager.com/envsoft/

## Cards Kanban EMS-10

| ID | Título | Status |
|----|--------|--------|
| TASK-014 | Zenodo DOI | doing |
| TASK-015 | Cover letter | done |
| TASK-016 | INPE 2025 + script | done |
| TASK-017 | BibTeX + ORCID | todo |
| TASK-018 | Copyedit nativo | todo |
| TASK-019 | Calibração sazonal LOO | done |
| TASK-020 | RAG ≥85% | done |
| TASK-021–029 | Ver kanban | todo/backlog |
