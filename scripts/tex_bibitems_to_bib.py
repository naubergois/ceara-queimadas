#!/usr/bin/env python3
"""Extract \\bibitem entries from artigo EN .tex into submission/refs-ems.bib."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "artigo-queimadas-gemeo-digital-en.tex"
OUT = ROOT / "submission" / "refs-ems.bib"


def main() -> None:
    text = TEX.read_text(encoding="utf-8")
    m = re.search(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", text, re.DOTALL)
    if not m:
        raise SystemExit("No thebibliography block found")

    block = m.group(0)
    items = re.findall(
        r"\\bibitem\{([^}]+)\}\s*\n((?:[^\\]|\\[^b]|\\b[^i]|\\bi[^b]|\\bib[^i])*?)(?=\\bibitem|\\end\{thebibliography\})",
        block,
        re.DOTALL,
    )

    lines = [
        "% Auto-generated from artigo-queimadas-gemeo-digital-en.tex for Elsevier EMS submission.",
        "% Regenerate: python scripts/tex_bibitems_to_bib.py",
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
        # Escape for BibTeX
        body = body.replace("\\", "")
        key_safe = re.sub(r"[^a-zA-Z0-9:._-]", "_", key)
        lines.append(f"@misc{{{key_safe},")
        lines.append(f"  author = {{Unknown}},")
        lines.append(f"  title = {{{body[:200]}}},")
        lines.append(f"  note = {{{body}}},")
        lines.append(f"  key = {{{key}}},")
        lines.append("}")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(items)} entries → {OUT}")


if __name__ == "__main__":
    main()
