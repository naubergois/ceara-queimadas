# Gêmeo Digital do Ceará — Queimadas: Visão e Pesquisa

## Objetivo da pesquisa

O projeto desenvolve um **gêmeo digital operacional** para monitoramento de queimadas no Estado do Ceará. A pesquisa integra:

- Dados de satélite em tempo quase real (NASA FIRMS VIIRS/MODIS, GOES-16)
- Dados climáticos territoriais (Open-Meteo, FUNCEME, INMET)
- Inteligência artificial agêntica (LangChain, LangGraph, DeepSeek)
- Interface web para gestores, Defesa Civil e pesquisadores

## Problema de pesquisa

Como apoiar a **detecção, validação, priorização e explicação** de focos de queimada no Ceará usando fontes abertas, sem depender exclusivamente de banco de dados institucional, mantendo **rastreabilidade** das decisões da IA?

## Hipóteses de trabalho

1. Cruzar NASA FIRMS com clima local melhora a interpretação do risco.
2. Agentes ReAct com ferramentas especializadas produzem respostas mais auditáveis que um LLM sem contexto.
3. Um índice vetorial (FAISS) com documentação do sistema permite explicar a aplicação a novos usuários sem treinar o modelo.

## Contribuições esperadas

- Plataforma demonstrável com dados reais no Ceará
- Pipeline de agentes (coleta → validação → diagnóstico → alerta)
- Modo standalone sem PostgreSQL para demonstração acadêmica e deploy EC2
- Chat de pesquisa (RAG) que documenta arquitetura e metodologia

## Público-alvo

- Pesquisadores e alunos (Unifor e parceiros)
- Gestores ambientais e Defesa Civil
- Desenvolvedores que estendem o gêmeo digital

## Contexto territorial

O Ceará apresenta forte sazonalidade de seca, biomas sensíveis (Caatinga, litoral) e pressão antrópica. O sistema filtra automaticamente focos dentro do bounding box: latitude -7,85 a -2,78 e longitude -41,42 a -37,25.
