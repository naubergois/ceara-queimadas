#!/usr/bin/env python3
"""Fix uncited references by editing the .tex file."""
with open('/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/artigo-queimadas-gemeo-digital.tex', 'r') as f:
    content = f.read()

# 1. Add GNN foundation refs
old = 'PyTorch Geometric~\\cite{article:pyg2019} usando convolução em grafos do tipo \\texttt{GCNConv}'
new = 'PyTorch Geometric~\\cite{article:pyg2019,article:xu2019,article:hamilton2017,article:velickovic2018,article:gin2022} usando convolução em grafos do tipo \\texttt{GCNConv}'
assert old in content, "GNN text not found!"
content = content.replace(old, new, 1)

# 2. Add Brazil-specific refs to Discussion
old2 = 'combinação de três sensores (VIIRS SNPP, VIIRS NOAA-20 e MODIS) garante múltiplas passagens por dia'
new2 = 'combinação de três sensores (VIIRS SNPP, VIIRS NOAA-20 e MODIS) garante múltiplas passagens por dia. Estudos específicos para biomas brasileiros \\cite{article:mccarty2024,article:alves2023,article:arruda2025} evidenciam tendências de atividade de fogo na América do Sul e a eficácia de aprendizado profundo para mapeamento de áreas queimadas na Amazônia e Caatinga'
assert old2 in content, "Discussion text not found!"
content = content.replace(old2, new2, 1)

# 3. Add RAG ref (izacard2022) to RAG section
old3 = 'RAG) \\cite{article:lewis2020,article:gao2024rag}'
new3 = 'RAG) \\cite{article:lewis2020,article:izacard2022,article:gao2024rag}'
assert old3 in content, "RAG text not found!"
content = content.replace(old3, new3, 1)

with open('/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/artigo-queimadas-gemeo-digital.tex', 'w') as f:
    f.write(content)

print("Done!")
