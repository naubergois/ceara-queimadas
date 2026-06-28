"""
EXP-ROBUST-004: Formal RAG retrieval benchmark (50 questions, recall@5, MRR).

Uses TF-IDF on knowledge chunks (same sources as FAISS index) — no GPU/API required.

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

QUESTIONS = [
    ("What is the LangGraph pipeline?", ["langgraph", "pipeline", "nó", "node"]),
    ("How many nodes does the agent pipeline have?", ["10", "dez", "nodes", "nós"]),
    ("What data sources does the platform use?", ["firms", "goes", "open-meteo", "inpe"]),
    ("What is NASA FIRMS?", ["firms", "viirs", "modis", "satellite"]),
    ("How is municipal risk classified?", ["risco", "risk", "classifier", "limiar"]),
    ("What is the ReAct agent used for?", ["react", "diagnos", "deepseek"]),
    ("What embedding model powers the RAG index?", ["bge", "embedding", "fastembed"]),
    ("What is FAISS used for?", ["faiss", "vector", "index", "retrieval"]),
    ("How to deploy on EC2?", ["ec2", "deploy", "docker", "systemd"]),
    ("What is NeKo-PIGNN?", ["neko", "pignn", "koopman", "gnn"]),
    ("What is the three-class detection system?", ["três", "three", "class", "incerteza", "uncertain"]),
    ("What precision does the YES alert class achieve?", ["82", "91", "precisão", "precision"]),
    ("What is the persistence prior?", ["persist", "prior", "semiárido"]),
    ("What frontend framework is used?", ["react", "vite", "typescript"]),
    ("What backend framework is used?", ["fastapi", "python", "uvicorn"]),
    ("Where is the knowledge base stored?", ["knowledge", "backend/knowledge"]),
    ("What is chunk size for RAG?", ["900", "chunk"]),
    ("What is top_k for retrieval?", ["top_k", "5", "recall"]),
    ("How does GOES-16 integration work?", ["goes", "abi", "cmipf", "s3"]),
    ("What is Open-Meteo used for?", ["open-meteo", "clima", "weather", "temperatura"]),
    ("What is the Canadian FWI?", ["fwi", "fire weather", "canadian"]),
    ("What is the Rothermel model?", ["rothermel", "propagation", "physics"]),
    ("What API endpoint handles research chat?", ["pesquisa", "chat", "/api"]),
    ("How to rebuild the FAISS index?", ["build_faiss", "faiss", "index"]),
    ("What is INPE BDQueimadas?", ["inpe", "bdqueimadas", "focos"]),
    ("What municipalities are monitored?", ["município", "fortaleza", "15"]),
    ("What is the risk index formula?", ["focos", "frp", "clima", "equação"]),
    ("What happens when DeepSeek times out?", ["fallback", "timeout", "rule"]),
    ("What is Track B in experiments?", ["track", "prediction", "083", "municipal"]),
    ("What split is used for model training?", ["70", "10", "20", "temporal"]),
    ("What is XGBoost used for?", ["xgboost", "gradient", "boost"]),
    ("What sensors contribute to FIRMS detections?", ["viirs", "snpp", "noaa", "modis"]),
    ("What is the geocoding service?", ["nominatim", "geocod"]),
    ("What license is the code under?", ["mit", "license", "open source"]),
    ("What is the operational deployment cost?", ["20", "usd", "ec2", "month"]),
    ("What is agent auditability?", ["audit", "thought", "action", "observation"]),
    ("What is the UNCERTAIN alert level?", ["incerteza", "uncertain", "watch", "goes"]),
    ("What is combined coverage YES plus UNCERTAIN?", ["88", "cobertura", "coverage"]),
    ("How long is the operational pipeline?", ["18", "months", "meses"]),
    ("What is Pydantic used for?", ["pydantic", "valid", "schema"]),
    ("What parallel analysis nodes exist?", ["geoespacial", "goes", "climatic", "parallel"]),
    ("What is the digital twin pragmatic definition?", ["digital twin", "mirror", "pragmatic"]),
    ("What biomes are in Ceará?", ["caatinga", "biome", "semiárido"]),
    ("What is the dry season in Ceará?", ["jul", "dez", "dry", "seca"]),
    ("How to run GOES validation?", ["unsupervised_fire_goes", "goes16"]),
    ("What is validate_real_data?", ["validate", "real", "benchmark"]),
    ("What is the alert threshold P(YES)?", ["0.3", "threshold", "limiar"]),
    ("What is LangGraph StateGraph?", ["stategraph", "state", "langgraph"]),
    ("What is the research chat module?", ["pesquisa", "rag", "chat"]),
    ("What documents are in the knowledge base?", ["01_visao", "knowledge", "06_deploy"]),
]


def chunk_documents(chunk_size: int = 900, overlap: int = 120) -> list[dict]:
    chunks = []
    for path in sorted(KNOWLEDGE.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end]
            chunks.append({"source": path.name, "text": chunk.lower()})
            start += chunk_size - overlap
    return chunks


def main() -> None:
    print("EXP-ROBUST-004: RAG benchmark (50 questions)")
    chunks = chunk_documents()
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(max_features=8000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)

    hits_at_5 = []
    mrrs = []
    details = []

    for q, keywords in QUESTIONS:
        q_vec = vectorizer.transform([q.lower()])
        sims = cosine_similarity(q_vec, matrix).flatten()
        top_idx = np.argsort(sims)[::-1][:5]
        top_chunks = [chunks[i] for i in top_idx]

        hit = False
        rank_hit = None
        for rank, ch in enumerate(top_chunks, 1):
            if any(kw.lower() in ch["text"] or kw.lower() in ch["source"].lower() for kw in keywords):
                hit = True
                rank_hit = rank
                break
        hits_at_5.append(1 if hit else 0)
        mrrs.append(1.0 / rank_hit if rank_hit else 0.0)
        details.append({"question": q, "hit@5": hit, "rank": rank_hit, "top_source": top_chunks[0]["source"] if top_chunks else ""})

    recall5 = float(np.mean(hits_at_5))
    mrr = float(np.mean(mrrs))

    payload = {
        "experiment": "EXP-ROBUST-004",
        "num_questions": len(QUESTIONS),
        "num_chunks": len(chunks),
        "recall_at_5": recall5,
        "mrr": mrr,
        "hits": int(sum(hits_at_5)),
        "details": details,
    }
    json_path = RESULTS_DIR / "EXP-ROBUST-004_rag.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    tex = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Formal RAG retrieval benchmark (50 questions, TF-IDF proxy of FAISS pipeline).}",
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
        f"- MRR: **{mrr:.3f}**\n",
        encoding="utf-8",
    )
    print(f"Recall@5={recall5:.1%}, MRR={mrr:.3f} → {json_path.name}")


if __name__ == "__main__":
    main()
