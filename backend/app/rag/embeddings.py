"""Embeddings leves para FAISS (fastembed — adequado para EC2)."""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_embeddings() -> Embeddings:
    try:
        from langchain_community.embeddings import FastEmbedEmbeddings

        logger.info("Embeddings FAISS (fastembed): %s", settings.FAISS_LOCAL_EMBEDDING_MODEL)
        return FastEmbedEmbeddings(model_name=settings.FAISS_LOCAL_EMBEDDING_MODEL)
    except Exception as e:
        logger.warning("fastembed indisponível (%s), fallback HuggingFace", e)
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=settings.FAISS_LOCAL_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
