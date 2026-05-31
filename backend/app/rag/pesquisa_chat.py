"""Chat RAG — explica a pesquisa e o funcionamento da aplicação."""

from __future__ import annotations

import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_factory import create_chat_llm, llm_is_configured
from app.rag.faiss_store import search_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o assistente do Gêmeo Digital do Ceará para Queimadas (projeto Unifor).
Sua função é explicar a PESQUISA, a ARQUITETURA e o FUNCIONAMENTO da aplicação para estudantes, gestores e desenvolvedores.

Regras:
- Responda SEMPRE em português do Brasil, de forma clara e didática.
- Use APENAS o contexto documental fornecido abaixo. Se a resposta não estiver no contexto, diga honestamente e sugira onde o usuário pode olhar na aplicação (mapa real, status das fontes, etc.).
- Não invente endpoints, tecnologias ou resultados experimentais que não apareçam no contexto.
- Quando útil, organize a resposta em tópicos curtos.
- Se perguntarem sobre focos ao vivo, explique que o mapa em /mapa-real consulta NASA FIRMS e que este chat é o guia da aplicação."""


async def responder_pergunta_pesquisa(pergunta: str) -> dict:
    docs = search_context(pergunta)
    contexto = "\n\n---\n\n".join(
        f"[{d.metadata.get('source', 'doc')}]\n{d.page_content}" for d in docs
    )
    fontes = list({d.metadata.get("source", "desconhecido") for d in docs})

    if not llm_is_configured():
        return {
            "pergunta": pergunta,
            "resposta": (
                "O índice FAISS está disponível, mas o DeepSeek não está configurado. "
                "Trechos relevantes da documentação:\n\n"
                + contexto[:3000]
            ),
            "fontes": fontes,
            "fragmentos_usados": len(docs),
            "modo": "somente_contexto",
            "gerado_em": datetime.utcnow().isoformat(),
        }

    llm = create_chat_llm(temperature=0.3, max_tokens=1200)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Contexto documental:\n{contexto}\n\n---\nPergunta do usuário: {pergunta}"
        ),
    ]
    msg = await llm.ainvoke(messages)
    texto = (msg.content or "").strip()

    return {
        "pergunta": pergunta,
        "resposta": texto,
        "fontes": fontes,
        "fragmentos_usados": len(docs),
        "modo": "deepseek_rag",
        "gerado_em": datetime.utcnow().isoformat(),
    }
