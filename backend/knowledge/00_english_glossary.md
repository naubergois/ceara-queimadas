# English glossary for RAG retrieval (bilingual index)

This document maps common operational and research questions (English) to platform facts documented in Portuguese modules.

## LangGraph pipeline
The production agent pipeline uses LangGraph StateGraph with **10 nodes**: coletar_dados, validar_dados, agente_geoespacial, agente_goes16, agente_climatico, fundir_evidencias, classificar_risco, agente_react_diagnostico, gerar_alertas, gerar_boletim.

## Data sources
NASA FIRMS (VIIRS SNPP, VIIRS NOAA-20, MODIS), optional GOES-16 ABI via AWS S3 CMIPF, INPE BDQueimadas CSV focos, Open-Meteo weather API, Canadian FWI.

## Three-class alerts
NO / UNCERTAIN / YES framework. YES alert threshold P(YES) >= 0.30. Combined YES+UNCERTAIN coverage 88%. YES precision 82-92% on short holdout; dry season 2025: 84.2% precision, 91.8% recall.

## NeKo-PIGNN
Neural Koopman Operator + Physics-Informed GNN with Rothermel regularization. Offline batch module (not LangGraph nodes). Synthetic R2=0.972.

## RAG and FAISS
Retrieval-Augmented Generation with FAISS vector index. Chunk size 900 characters. top_k=5 for retrieval. Embedding: BGE via fastembed. Rebuild: scripts/build_faiss_index.py. Knowledge base: backend/knowledge/*.md

## ReAct agent
ReAct Thought-Action-Observation cycles with DeepSeek. Rule-based fallback on timeout. 97% success on 100 operational questions.

## Deployment
EC2 t2.medium ~USD 20/month. deploy/unifor-deploy.sh installs nginx, Python 3.12, Node.js 20, systemd unifor-backend. Docker Compose full mode with PostGIS.

## Frontend and backend
React 19 + Vite 8 + TypeScript frontend. FastAPI + Python backend. Pydantic schemas. Research chat API /api/v1/pesquisa.

## Experiments
Track B municipal prediction. Temporal split 70/10/20. EXP-ROBUST-001 bootstrap CI. EXP-ROBUST-003 extended temporal INPE. validate_real_data benchmark.

## GOES-16
GOES-16 integration via agente_goes16 node. unsupervised_fire_goes validation script. Pixel-level F1 ~0.034 vs INPE.

## Risk classifier
Heuristic municipal risk index: focos, FRP, clima_seca weights. Calibrated against INPE BDQueimadas F1=0.936.

## License
MIT open-source license. Repository: github.com/naubergois/ceara-queimadas

## Persistence prior
Semi-arid fire day-to-day continuity prior for semi-arid Ceará (Caatinga biome). Dry season July-December.

## Geocoding
Nominatim async geocoding for hotspot municipalities. Monitors top 15 municipalities including Fortaleza, Sobral, Juazeiro do Norte.
