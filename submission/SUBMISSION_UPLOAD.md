# EMS Submission — pronto para upload (TASK-029)

**Gerar/atualizar:** `./scripts/build_ems_submission_package.sh`  
**Release + Zenodo:** `./scripts/publish_zenodo_deposit.sh`

## Pacote principal

| Arquivo | Uso |
|---------|-----|
| **`submission/EMS_SUBMISSION_PACKAGE.zip`** | Upload completo (~15 MB) |
| `submission/EMS_SUBMISSION_PACKAGE/` | Mesmo conteúdo descompactado |

## Passo a passo — Editorial Manager

1. Acesse https://www.editorialmanager.com/envsoft/
2. **Submit New Manuscript** → Article type: **Research Article**
3. Anexe os arquivos 01–06 da pasta `EMS_SUBMISSION_PACKAGE/` (ver tabela em `checklist_envmod.md`)
4. Cole os **Highlights** de `04_Highlights.txt` no campo dedicado (se separado do upload)
5. Registre **ORCID** de cada autor (`ORCID_AUTHORS.md`)
6. Revisores sugeridos (cover letter):
   - Steven L. Brunton (UW)
   - George Em Karniadakis (Brown)
   - Alan A. Ager (USDA Forest Service)
7. Declarations: sem conflito de interesse; uso de IA declarado no manuscrito
8. **Submit**

## Reproducibility (TASK-014)

| Recurso | URL / arquivo |
|---------|----------------|
| GitHub release | https://github.com/naubergois/ceara-queimadas/releases/tag/v1.0.0-ems-submission |
| Zenodo bundle | `07_Zenodo_Reproducibility_Bundle.zip` |
| Mint DOI | `export ZENODO_ACCESS_TOKEN=... && ./scripts/publish_zenodo_deposit.sh` |

## Validação (última build)

- Manuscrito: **49 páginas** · Abstract **123 palavras** · **7 keywords**
- Highlights: **5 bullets**, todos ≤85 caracteres
- 0 erros LaTeX · 0 citações indefinidas

## Pendente só no portal

- [ ] Login Editorial Manager + upload 01–06
- [ ] Confirmar ORCID no EM
- [ ] (Opcional) Zenodo DOI após token
