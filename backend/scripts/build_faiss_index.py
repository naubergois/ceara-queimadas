#!/usr/bin/env python3
"""Gera o índice FAISS a partir de backend/knowledge/*.md"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.faiss_store import build_faiss_index, index_status, knowledge_dir


def main() -> int:
    if not list(knowledge_dir().glob("*.md")):
        print(f"Nenhum arquivo em {knowledge_dir()}", file=sys.stderr)
        return 1
    print("Construindo índice FAISS...")
    build_faiss_index(force=True)
    st = index_status()
    print(f"OK — documentos: {st['documentos_fonte']}, índice: {st['caminho']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
