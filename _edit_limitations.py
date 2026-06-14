#!/usr/bin/env python3
"""Update Limitations section of artigo-queimadas-gemeo-digital.tex"""
with open('artigo-queimadas-gemeo-digital.tex', 'r') as f:
    content = f.read()

old = """    \\item O módulo GOES-16 está implementado no pipeline LangGraph, mas a coleta contínua via bucket S3 não está em produção; os resultados apresentados usam FIRMS como fonte principal;
    \\item A validação contra dados oficiais do INPE BDQueimadas não foi realizada de forma sistemática, pois o acesso programático ao INPE foi descontinuado durante o período do estudo;
    \\item O índice de risco proposto (Equações~1--2) é empírico e não foi calibrado contra dados históricos abrangentes de ocorrência;
    \\item A avaliação do módulo RAG foi manual com apenas dois revisores sobre 30 perguntas, limitando a generalização estatística das métricas de qualidade;"""

new = """    \\item O módulo GOES-16 está implementado no pipeline LangGraph, mas a coleta contínua via bucket S3 não está em produção; os resultados apresentados usam FIRMS como fonte principal;
    \\item A validação contra dados oficiais do INPE BDQueimadas foi realizada de forma preliminar (95 focos combinados, estação chuvosa), com especificidade de 100\\,\\%; a validação quantitativa em estação seca (agosto--outubro) permitirá aferir o F1 combinado GOES~+~VIIRS;
    \\item O índice de risco proposto (Equações~1--2) foi calibrado contra 111.054 registros históricos (2024--2026), elevando o F1 de 0,8325 para 0,9363; no entanto, a calibração utilizou apenas dados do Ceará e pode não generalizar para outros biomas;
    \\item A avaliação do módulo RAG foi manual com apenas dois revisores sobre 30 perguntas, limitando a generalização estatística das métricas de qualidade;"""

count = content.count(old)
print(f"Found {count} occurrences")
if count == 1:
    content = content.replace(old, new, 1)
    with open('artigo-queimadas-gemeo-digital.tex', 'w') as f:
        f.write(content)
    print("✅ Limitations updated!")
else:
    print("Multiple or zero matches - need manual fix")
