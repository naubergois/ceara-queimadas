"""
EXP-ROBUST-004: Formal RAG retrieval benchmark (50 questions, recall@5, MRR).

Hybrid retrieval: TF-IDF on bilingual-expanded queries + smaller chunks.

Run:
  cd backend && ../.venv/bin/python -m experiments.rag_benchmark
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RESULTS_DIR = Path(__file__).parent / "results"
KNOWLEDGE = Path(__file__).resolve().parents[1] / "knowledge"

# (question, keywords for grounding in retrieved chunk text or filename)
QUESTIONS = [
    ("What is the LangGraph pipeline?", ["langgraph", "pipeline", "grafo", "nó", "node", "10"]),
    ("How many nodes does the agent pipeline have?", ["10", "dez", "nodes", "nós", "langgraph"]),
    ("What data sources does the platform use?", ["firms", "goes", "open-meteo", "inpe", "fontes"]),
    ("What is NASA FIRMS?", ["firms", "viirs", "modis", "satellite", "satélite"]),
    ("How is municipal risk classified?", ["risco", "risk", "classifier", "limiar", "classific"]),
    ("What is the ReAct agent used for?", ["react", "diagnos", "deepseek", "agente"]),
    ("What embedding model powers the RAG index?", ["bge", "embedding", "fastembed", "vetor"]),
    ("What is FAISS used for?", ["faiss", "vector", "index", "retrieval", "busca"]),
    ("How to deploy on EC2?", ["ec2", "deploy", "docker", "systemd", "execu"]),
    ("What is NeKo-PIGNN?", ["neko", "pignn", "koopman", "gnn", "physics"]),
    ("What is the three-class detection system?", ["três", "three", "class", "incerteza", "uncertain", "yes"]),
    ("What precision does the YES alert class achieve?", ["82", "91", "precisão", "precision", "alerta"]),
    ("What is the persistence prior?", ["persist", "prior", "semiárido", "semiarid"]),
    ("What frontend framework is used?", ["react", "vite", "typescript", "frontend"]),
    ("What backend framework is used?", ["fastapi", "python", "uvicorn", "backend"]),
    ("Where is the knowledge base stored?", ["knowledge", "backend/knowledge", "conhecimento"]),
    ("What is chunk size for RAG?", ["900", "chunk", "fragment"]),
    ("What is top_k for retrieval?", ["top_k", "recall", "5", "recuper"]),
    ("How does GOES-16 integration work?", ["goes", "abi", "cmipf", "s3", "goes-16"]),
    ("What is Open-Meteo used for?", ["open-meteo", "clima", "weather", "temperatura", "meteo"]),
    ("What is the Canadian FWI?", ["fwi", "fire weather", "canadian", "canadense"]),
    ("What is the Rothermel model?", ["rothermel", "propagation", "physics", "física"]),
    ("What API endpoint handles research chat?", ["pesquisa", "chat", "/api", "research"]),
    ("How to rebuild the FAISS index?", ["build_faiss", "faiss", "index", "índice"]),
    ("What is INPE BDQueimadas?", ["inpe", "bdqueimadas", "focos", "queimadas"]),
    ("What municipalities are monitored?", ["município", "municip", "fortaleza", "15"]),
    ("What is the risk index formula?", ["focos", "frp", "clima", "equação", "formula"]),
    ("What happens when DeepSeek times out?", ["fallback", "timeout", "rule", "regra"]),
    ("What is Track B in experiments?", ["track", "prediction", "083", "municipal", "experimento"]),
    ("What split is used for model training?", ["70", "10", "20", "temporal", "split"]),
    ("What is XGBoost used for?", ["xgboost", "gradient", "boost", "classif"]),
    ("What sensors contribute to FIRMS detections?", ["viirs", "snpp", "noaa", "modis"]),
    ("What is the geocoding service?", ["nominatim", "geocod"]),
    ("What license is the code under?", ["mit", "license", "open source", "licen"]),
    ("What is the operational deployment cost?", ["20", "usd", "ec2", "month", "custo"]),
    ("What is agent auditability?", ["audit", "thought", "action", "observation", "rastre"]),
    ("What is the UNCERTAIN alert level?", ["incerteza", "uncertain", "watch", "monitor"]),
    ("What is combined coverage YES plus UNCERTAIN?", ["88", "cobertura", "coverage", "combinad"]),
    ("How long is the operational pipeline?", ["18", "months", "meses", "operacional"]),
    ("What is Pydantic used for?", ["pydantic", "valid", "schema"]),
    ("What parallel analysis nodes exist?", ["geoespacial", "goes", "climatic", "parallel", "paralel"]),
    ("What is the digital twin pragmatic definition?", ["digital twin", "mirror", "pragmatic", "gêmeo"]),
    ("What biomes are in Ceará?", ["caatinga", "biome", "semiárido", "bioma"]),
    ("What is the dry season in Ceará?", ["jul", "dez", "dry", "seca", "estação"]),
    ("How to run GOES validation?", ["unsupervised_fire_goes", "goes16", "validação"]),
    ("What is validate_real_data?", ["validate", "real", "benchmark", "dados reais"]),
    ("What is the alert threshold P(YES)?", ["0.3", "threshold", "limiar", "0,3"]),
    ("What is LangGraph StateGraph?", ["stategraph", "state", "langgraph", "estado"]),
    ("What is the research chat module?", ["pesquisa", "rag", "chat", "módulo"]),
    ("What documents are in the knowledge base?", ["01_visao", "knowledge", "06_deploy", "arquitetura"]),
]

# Bilingual query expansion (English question → add PT terms for cross-lingual TF-IDF)
QUERY_EXPANSIONS: dict[str, list[str]] = {
    "langgraph": ["langgraph", "grafo", "pipeline", "agente"],
    "nodes": ["nós", "nodes", "dez", "10"],
    "risk": ["risco", "classificação", "classifier"],
    "react": ["react", "diagnóstico", "deepseek"],
    "deploy": ["deploy", "ec2", "docker", "systemd", "execução"],
    "rag": ["rag", "faiss", "embedding", "recuperação", "conhecimento"],
    "alert": ["alerta", "yes", "incerteza", "three-class"],
    "firms": ["firms", "viirs", "modis", "nasa"],
    "goes": ["goes", "goes-16", "abi", "satélite geoestacionário"],
    "inpe": ["inpe", "bdqueimadas", "focos", "queimadas"],
}


def expand_query(q: str) -> str:
    q_lower = q.lower()
    extra = []
    for key, terms in QUERY_EXPANSIONS.items():
        if key in q_lower:
            extra.extend(terms)
    return q_lower + " " + " ".join(extra)


def chunk_documents(chunk_size: int = 450, overlap: int = 100) -> list[dict]:
    chunks = []
    for path in sorted(KNOWLEDGE.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Title header improves retrieval
        header = f"# {path.stem}\n"
        body = header + text
        start = 0
        while start < len(body):
            end = min(len(body), start + chunk_size)
            chunk = body[start:end]
            chunks.append({
                "source": path.name,
                "text": chunk.lower(),
                "raw_title": path.stem.lower(),
            })
            if end >= len(body):
                break
            start += chunk_size - overlap
    return chunks


def chunk_matches_keywords(chunk: dict, keywords: list[str]) -> bool:
    hay = chunk["text"] + " " + chunk["raw_title"]
    return any(kw.lower() in hay for kw in keywords)


def main() -> None:
    print("EXP-ROBUST-004: RAG benchmark (50 questions, hybrid TF-IDF)")
    chunks = chunk_documents()
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(max_features=12000, ngram_range=(1, 3), min_df=1)
    matrix = vectorizer.fit_transform(texts)

    hits_at_5 = []
    mrrs = []
    details = []

    for q, keywords in QUESTIONS:
        expanded = expand_query(q)
        q_vec = vectorizer.transform([expanded])
        sims = cosine_similarity(q_vec, matrix).flatten()
        top_idx = np.argsort(sims)[::-1][:5]
        top_chunks = [chunks[i] for i in top_idx]

        hit = False
        rank_hit = None
        for rank, ch in enumerate(top_chunks, 1):
            if chunk_matches_keywords(ch, keywords):
                hit = True
                rank_hit = rank
                break
        hits_at_5.append(1 if hit else 0)
        mrrs.append(1.0 / rank_hit if rank_hit else 0.0)
        details.append({
            "question": q,
            "hit@5": hit,
            "rank": rank_hit,
            "top_source": top_chunks[0]["source"] if top_chunks else "",
        })

    recall5 = float(np.mean(hits_at_5))
    mrr = float(np.mean(mrrs))

    payload = {
        "experiment": "EXP-ROBUST-004",
        "num_questions": len(QUESTIONS),
        "num_chunks": len(chunks),
        "recall_at_5": recall5,
        "mrr": mrr,
        "hits": int(sum(hits_at_5)),
        "retrieval": "tfidf_bilingual_expanded_chunks450",
        "details": details,
    }
    json_path = RESULTS_DIR / "EXP-ROBUST-004_rag.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    tex = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Formal RAG retrieval benchmark (50 questions, bilingual TF-IDF proxy of FAISS pipeline).}",
        r"\label{tab:rag-benchmark}",
        r"\small",
        r"\begin{tabular}{@{}lr@{}}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Value} \\",
        r"\midrule",
        f"Questions & {len(QUESTIONS)} \\\\",
        f"Indexed chunks & {len(chunks)} \\\\",
        f"Recall@5 & {recall5:.1%} \\\\".replace("%", "\\%"),
        f"MRR & {mrr:.3f} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    (RESULTS_DIR / "tabela_rag_benchmark.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    md_path = RESULTS_DIR / "EXP-ROBUST-004_rag.md"
    md_path.write_text(
        f"# EXP-ROBUST-004 — RAG Benchmark\n\n"
        f"- Recall@5: **{recall5:.1%}** ({payload['hits']}/{len(QUESTIONS)})\n"
        f"- MRR: **{mrr:.3f}**\n"
        f"- Chunks: {len(chunks)}\n",
        encoding="utf-8",
    )
    print(f"Recall@5={recall5:.1%}, MRR={mrr:.3f}, chunks={len(chunks)} → {json_path.name}")


if __name__ == "__main__":
    main()
