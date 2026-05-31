#!/usr/bin/env python3
"""Copia DEEPSEEK_* de projetos irmãos (AIManager, GerenciaTreinamentos, etc.) para backend/.env."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.secrets_fallback import _SIBLING_ENV_FILES, _is_placeholder, _parse_env_file

TARGET = ROOT / ".env"
VARS = ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "DEEPSEEK_MODEL")


def main() -> int:
    source_path = None
    source_data: dict[str, str] = {}
    for path in _SIBLING_ENV_FILES:
        if not path.is_file():
            continue
        data = _parse_env_file(path)
        if not _is_placeholder(data.get("DEEPSEEK_API_KEY", "")):
            source_path = path
            source_data = data
            break

    if not source_path:
        print("Nenhuma chave DeepSeek encontrada nos projetos irmãos.", file=sys.stderr)
        return 1

    lines: list[str] = []
    if TARGET.is_file():
        lines = TARGET.read_text(encoding="utf-8").splitlines()

    updated = dict(source_data)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in VARS and key in updated:
                out.append(f"{key}={updated[key]}")
                seen.add(key)
                continue
        out.append(line)

    for key in VARS:
        if key not in seen and key in updated:
            out.append(f"{key}={updated[key]}")

    if not any("DEEPSEEK_API_BASE" in ln for ln in out):
        out.append("DEEPSEEK_API_BASE=https://api.deepseek.com")
    if not any("DEEPSEEK_MODEL" in ln for ln in out):
        out.append("DEEPSEEK_MODEL=deepseek-chat")

    TARGET.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"DeepSeek sincronizado de {source_path} → {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
