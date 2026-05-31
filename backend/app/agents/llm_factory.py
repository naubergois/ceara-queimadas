"""Factory LangChain — DeepSeek (OpenAI-compatible API)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.secrets_fallback import deepseek_from_siblings, resolve_deepseek_api_key


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return True
    return v.startswith("your_") or v in {"changeme", "xxx", "placeholder"}


def get_deepseek_api_key() -> str:
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    if key and not _is_placeholder(key):
        return key
    resolved = resolve_deepseek_api_key()
    return resolved or ""


def get_deepseek_base_url() -> str:
    if settings.DEEPSEEK_API_BASE and not _is_placeholder(settings.DEEPSEEK_API_BASE):
        return settings.DEEPSEEK_API_BASE.rstrip("/")
    siblings = deepseek_from_siblings()
    base = siblings.get("deepseek_api_base", "").strip()
    return (base or "https://api.deepseek.com").rstrip("/")


def get_deepseek_model() -> str:
    if settings.DEEPSEEK_MODEL and not _is_placeholder(settings.DEEPSEEK_MODEL):
        return settings.DEEPSEEK_MODEL
    siblings = deepseek_from_siblings()
    return siblings.get("deepseek_model") or "deepseek-chat"


def llm_is_configured() -> bool:
    return bool(get_deepseek_api_key())


def create_chat_llm(*, temperature: float = 0.1, max_tokens: int | None = None) -> ChatOpenAI:
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError(
            "DeepSeek não configurado. Defina DEEPSEEK_API_KEY no backend/.env "
            "ou rode: python scripts/sync_deepseek_env.py"
        )
    kwargs: dict = {
        "model": get_deepseek_model(),
        "api_key": api_key,
        "base_url": get_deepseek_base_url(),
        "temperature": temperature,
        "timeout": 120.0,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)
