"""API do chat RAG — pesquisa e manual da aplicação."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.llm_factory import llm_is_configured
from app.rag.faiss_store import build_faiss_index, index_status, load_faiss_index
from app.rag.pesquisa_chat import responder_pergunta_pesquisa

router = APIRouter(prefix="/pesquisa", tags=["Chat Pesquisa"])


class ChatPesquisaRequest(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=2000)


class ChatPesquisaResponse(BaseModel):
    pergunta: str
    resposta: str
    fontes: list[str]
    fragmentos_usados: int
    modo: str
    gerado_em: str


@router.get("/status")
async def status_pesquisa():
    """Status do índice FAISS e do LLM."""
    st = index_status()
    st["deepseek_configurado"] = llm_is_configured()
    return st


@router.post("/chat", response_model=ChatPesquisaResponse)
async def chat_pesquisa(payload: ChatPesquisaRequest):
    """
    Chat com RAG sobre a pesquisa e o funcionamento da aplicação.
    Usa FAISS + documentação em backend/knowledge/.
    """
    try:
        load_faiss_index()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Índice FAISS indisponível: {e}") from e

    try:
        result = await responder_pergunta_pesquisa(payload.pergunta.strip())
        return ChatPesquisaResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no chat: {e}") from e


@router.post("/reindex")
async def reindex_pesquisa():
    """Reconstrói o índice FAISS a partir de backend/knowledge/ (admin)."""
    try:
        build_faiss_index(force=True)
        return {"ok": True, **index_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
