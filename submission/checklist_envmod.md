# Checklist de Submissão — Environmental Modelling & Software

## 📋 Pré-requisitos da Revista

- [x] **Template Elsevier**: elsarticle.cls (formato 5p, twocolumn)
- [x] **Título**: "Neural Koopman Operator + Physics-Informed Graph Neural Networks for Real-Time Wildfire Digital Twin"
- [x] **Autores**: Nauber Gois (único autor)
- [x] **Abstract**: Bilíngue (PT + EN) — 150-250 palavras
- [x] **Highlights**: 3-5 bullet points (máx. 85 caracteres cada)
- [x] **Keywords**: 6-10 palavras-chave
- [x] **Figuras**: PNG ≥1200px, 200dpi, formato Environmental Modelling & Software
- [x] **Tabelas**: Formato LaTeX (\begin{table}...\end{table})
- [x] **Referências**: BibTeX, estilo Elsevier (harvard)
- [x] **Carta de Submissão**: Cover letter com novelty statement

## 📄 Documentos Entregues

| Documento | Status | Arquivo |
|-----------|--------|---------|
| Artigo LaTeX (PT) | ✅ | `artigo-queimadas-gemeo-digital.tex` |
| Artigo LaTeX (EN) | ✅ | `artigo-queimadas-gemeo-digital-en.tex` |
| Cover Letter | ✅ | `submission/cover_letter.tex` |
| Abstract PT | ✅ | No artigo |
| Abstract EN | ✅ | No artigo |
| Highlights | ✅ | `submission/highlights.txt` |
| Sugestão Revisores | ✅ | Na cover letter |
| Checklist | ✅ | Este arquivo |
| Índice experimentos | ✅ | `docs/experimentos/README.md` |
| Protocolo LaTeX | ✅ | `figures/experimentos-artigo.tex` |

## 🎨 Figuras

| Figura | Arquivo | Resolução | Status |
|--------|---------|-----------|--------|
| Diagrama Arquitetura | `figures/architecture.png` | 1960×1868px | ✅ |
| Pipeline LangGraph | `figures/langgraph.png` | 1476×2388px | ✅ |
| Diagrama Koopman | `figures/diagrama-koopman-pignn.png` | 4000×2500px | ✅ |
| Resultados Experimentais | `figures/resultados-experimentais.png` | 1600×1000px | ✅ |
| Evolução Focos | `figures/evolucao-focos.png` | 2000×1000px | ✅ |
| Tabela Comparativa | `figures/tabela-comparativa.tex` | LaTeX | ✅ |

## 🔬 Checklist Científico

- [x] Metodologia matemática (15 equações) documentada
- [x] Benchmark comparativo (5 modelos: Rothermel, CNN, GNN, Neural ODE, NeKo-PIGNN)
- [x] Estudo de ablação (Koopman sem PINN, PI-GNN sem Koopman, completo)
- [x] Dados reais VIIRS/GOES-16 (Ceará, Brasil)
- [x] Resultados reprodutíveis (código PyTorch open-source)
- [x] Agente explicador ReAct com DeepSeek (INOV-009)
- [x] Dashboard React interativo (INOV-005)
- [x] Artigo compilado com pdflatex (7+ páginas)

## 📮 Passos para Submissão

1. [ ] Compilar PDF final com pdflatex (3×)
2. [ ] Verificar formatação elsarticle
3. [ ] Converter figuras para EPS (se revista exigir)
4. [ ] Submeter em: https://www.editorialmanager.com/envsoft/
5. [ ] Anexar: Manuscript (PDF), Cover Letter, Highlights, Figuras (separadas)
6. [ ] Sugerir 3 revisores
7. [ ] Submeter e aguardar desk decision (~2-4 semanas)

## 💡 Dicas para Submissão

1. **Título chamativo**: Incluir "Neural Koopman" + "Physics-Informed" + "Digital Twin"
2. **Highlights**: Foco no gap (ZERO publicações combinando Koopman + PI-GNN para fogo)
3. **Dados abertos**: Código no GitHub + dados FIRMS públicos
4. **Aplicação real**: Ceará queima ~10.000 km²/ano — relevância prática
5. **Reprodutibilidade**: Scripts Python + Docker Compose

