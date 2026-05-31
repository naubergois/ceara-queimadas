"""Construção e consulta do índice FAISS da documentação da aplicação."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

_vectorstore: Optional[FAISS] = None


def knowledge_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge"


def index_dir() -> Path:
    p = Path(settings.FAISS_INDEX_DIR)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def load_knowledge_documents() -> list[Document]:
    docs: list[Document] = []
    kdir = knowledge_dir()
    if not kdir.is_dir():
        logger.warning("Pasta knowledge não encontrada: %s", kdir)
        return docs

    for path in sorted(kdir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=text,
                metadata={"source": path.name, "titulo": path.stem.replace("_", " ")},
            )
        )
    return docs


def build_faiss_index(*, force: bool = False) -> FAISS:
    """Fragmenta knowledge/*.md e persiste índice FAISS em disco."""
    global _vectorstore

    out = index_dir()
    index_file = out / "index.faiss"
    if index_file.exists() and not force:
        return load_faiss_index()

    raw_docs = load_knowledge_documents()
    if not raw_docs:
        raise FileNotFoundError(f"Nenhum .md em {knowledge_dir()}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.FAISS_CHUNK_SIZE,
        chunk_overlap=settings.FAISS_CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    chunks = splitter.split_documents(raw_docs)
    logger.info("Indexando %d fragmentos de %d documentos", len(chunks), len(raw_docs))

    embeddings = get_embeddings()
    store = FAISS.from_documents(chunks, embeddings)
    out.mkdir(parents=True, exist_ok=True)
    store.save_local(str(out))
    _vectorstore = store
    logger.info("Índice FAISS salvo em %s", out)
    return store


def load_faiss_index() -> FAISS:
    """Carrega índice do disco."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    out = index_dir()
    if not (out / "index.faiss").exists():
        return build_faiss_index()

    embeddings = get_embeddings()
    _vectorstore = FAISS.load_local(
        str(out),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    logger.info("Índice FAISS carregado (%s)", out)
    return _vectorstore


def search_context(query: str, k: int | None = None) -> list[Document]:
    store = load_faiss_index()
    return store.similarity_search(query, k=k or settings.FAISS_TOP_K)


def index_status() -> dict:
    out = index_dir()
    ready = (out / "index.faiss").exists()
    n_docs = len(list(knowledge_dir().glob("*.md"))) if knowledge_dir().is_dir() else 0
    n_chunks = 0
    if _vectorstore is not None:
        try:
            n_chunks = len(_vectorstore.docstore._dict)  # type: ignore[attr-defined]
        except Exception:
            n_chunks = -1
    return {
        "indice_pronto": ready,
        "caminho": str(out),
        "documentos_fonte": n_docs,
        "fragmentos_indexados": n_chunks if n_chunks >= 0 else None,
    }
