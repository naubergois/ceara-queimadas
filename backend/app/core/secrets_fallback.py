"""Reutiliza DEEPSEEK_* de projetos irmãos quando o .env local não tem chave."""

from __future__ import annotations

import os
from pathlib import Path

_SIBLING_ENV_FILES = (
    Path.home() / "AIManager/.env",
    Path.home() / "AIManager/jangada/.env",
    Path.home() / "GerenciaTreinamentos/.env",
    Path.home() / "Eleicoes/.env",
    Path.home() / "curso_orquestracao_agentes_langchain/.env",
    Path("/Volumes/NAUBER/GerenciaTreinamentos/.env"),
    Path("/Volumes/NAUBER/Eleicoes/.env"),
)

_DEEPSEEK_VARS = ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "DEEPSEEK_MODEL")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return True
    return v.startswith("your_") or v in {"changeme", "xxx", "placeholder"}


def deepseek_from_siblings() -> dict[str, str]:
    """Lê DEEPSEEK_* do primeiro .env irmão com chave válida."""
    for path in _SIBLING_ENV_FILES:
        if not path.is_file():
            continue
        data = _parse_env_file(path)
        key = data.get("DEEPSEEK_API_KEY", "")
        if _is_placeholder(key):
            continue
        result: dict[str, str] = {"deepseek_api_key": key}
        if data.get("DEEPSEEK_API_BASE"):
            result["deepseek_api_base"] = data["DEEPSEEK_API_BASE"]
        if data.get("DEEPSEEK_MODEL"):
            result["deepseek_model"] = data["DEEPSEEK_MODEL"]
        return result
    return {}


def resolve_deepseek_api_key() -> str | None:
    """Chave DeepSeek: env explícita > .env do backend > projetos irmãos."""
    explicit = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if explicit and not _is_placeholder(explicit):
        return explicit

    backend_env = Path(__file__).resolve().parents[2] / ".env"
    if backend_env.is_file():
        key = _parse_env_file(backend_env).get("DEEPSEEK_API_KEY", "")
        if key and not _is_placeholder(key):
            return key

    return deepseek_from_siblings().get("deepseek_api_key")
