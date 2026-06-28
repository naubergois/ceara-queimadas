#!/usr/bin/env python3
"""Normalize submission/refs-ems.bib for elsarticle-num (year + escaped note)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "submission" / "refs-ems.bib"
TEX = ROOT / "artigo-queimadas-gemeo-digital-en.tex"


def escape_bib(s: str) -> str:
    return s.replace("&", r"\&").replace("%", r"\%")


def regenerate_from_git() -> None:
    """Rebuild .bib from last committed inline thebibliography."""
    old_tex = subprocess.check_output(
        ["git", "show", "HEAD:artigo-queimadas-gemeo-digital-en.tex"],
        text=True,
        cwd=ROOT,
    )
    m = re.search(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", old_tex, re.DOTALL)
    if not m:
        raise SystemExit("No thebibliography in HEAD commit")
    block = m.group(0)
    items = re.findall(
        r"\\bibitem\{([^}]+)\}\s*\n((?:[^\\]|\\[^b]|\\b[^i]|\\bi[^b]|\\bib[^i])*?)(?=\\bibitem|\\end\{thebibliography\})",
        block,
        re.DOTALL,
    )
    lines = [
        "% Elsevier EMS BibTeX — Environmental Modelling & Software",
        "% Regenerate: python scripts/normalize_refs_ems_bib.py --from-git",
        "",
    ]
    for key, body in items:
        body = re.sub(r"%.*", "", body)
        body = " ".join(body.split())
        body = body.replace("{", "").replace("}", "")
        body = body.replace("\\textit", "").replace("\\emph", "")
        body = body.replace("``", '"').replace("''", '"')
        body = body.replace("\\url", "URL:")
        body = body.replace("~", " ")
        body = body.replace("\\&", "&")
        body = re.sub(r"\\[a-zA-Z]+", "", body)
        body = " ".join(body.split())
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", body)
        year = years[-1] if years else ""
        note = escape_bib(body)
        lines.append(f"@misc{{{key},")
        if year:
            lines.append(f"  year = {{{year}}},")
        lines.append(f"  note = {{{note}}},")
        lines.append("}")
        lines.append("")
    BIB.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"Regenerated {len(items)} entries → {BIB}")


def normalize_existing() -> None:
    text = BIB.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=@misc\{)", text)
    header = blocks[0].strip()
    out = [header] if header else []
    count = 0
    for block in blocks:
        if not block.strip().startswith("@misc"):
            continue
        m_key = re.search(r"@misc\{([^,]+),", block)
        m_note = re.search(r"note = \{([^}]*)\}", block, re.DOTALL)
        if not m_key or not m_note:
            continue
        key = m_key.group(1).strip()
        note = m_note.group(1).strip().replace("&", r"\&")
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", note)
        year = years[-1] if years else ""
        out.append(f"@misc{{{key},")
        if year:
            out.append(f"  year = {{{year}}},")
        out.append(f"  note = {{{note}}},")
        out.append("}")
        out.append("")
        count += 1
    BIB.write_text("\n".join(out).strip() + "\n", encoding="utf-8")
    print(f"Normalized {count} entries → {BIB}")


if __name__ == "__main__":
    import sys
    if "--from-git" in sys.argv:
        regenerate_from_git()
    else:
        normalize_existing()
