#!/usr/bin/env python3
"""
Validate submission/refs-ems.bib against Crossref (DOIs) and arXiv (eprints).

For every entry with a DOI, fetch https://api.crossref.org/works/{doi} and
compare title similarity and year. For arXiv-only entries, query the arXiv
export API. Entries without DOI/eprint (manuals, tech reports, theses) are
listed as UNCHECKED.

Output: a per-entry report (OK / MISMATCH / NOT FOUND / UNCHECKED) on stdout
and a JSON report at /tmp/refs_validation.json.

Run: python3 scripts/validate_refs_crossref.py
"""

import json
import re
import time
import urllib.request
import urllib.error
from difflib import SequenceMatcher
from pathlib import Path

BIB = Path(__file__).parent.parent / "submission" / "refs-ems.bib"
HEADERS = {"User-Agent": "refs-validator/1.0 (mailto:naubergois@gmail.com)"}


def parse_bib(text: str) -> list[dict]:
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", text, re.DOTALL):
        etype, key, body = m.group(1), m.group(2).strip(), m.group(3)
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries.append({"type": etype, "key": key, **fields})
    return entries


def norm(s: str) -> str:
    s = re.sub(r"[{}\\'\"`^~]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def check_crossref(entry: dict) -> dict:
    doi = entry["doi"].strip()
    data = fetch_json(f"https://api.crossref.org/works/{urllib.request.quote(doi)}")
    if data is None:
        return {"status": "NOT_FOUND", "detail": f"DOI {doi} not registered in Crossref"}
    msg = data["message"]
    cr_title = (msg.get("title") or [""])[0]
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(k) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    sim = similarity(entry.get("title", ""), cr_title)
    bib_year = int(entry.get("year", 0) or 0)
    problems = []
    if sim < 0.75:
        problems.append(f"title mismatch (sim={sim:.2f}): Crossref='{cr_title[:90]}'")
    if year and bib_year and abs(year - bib_year) > 1:
        problems.append(f"year mismatch: bib={bib_year}, Crossref={year}")
    cont = msg.get("container-title") or []
    detail = {
        "crossref_title": cr_title,
        "crossref_year": year,
        "crossref_container": cont[0] if cont else "",
        "title_similarity": round(sim, 3),
    }
    if problems:
        return {"status": "MISMATCH", "problems": problems, **detail}
    return {"status": "OK", **detail}


def check_arxiv(entry: dict) -> dict:
    arxiv_id = entry["eprint"].strip()
    xml = fetch_text(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
    m = re.search(r"<entry>.*?<title>(.*?)</title>", xml, re.DOTALL)
    if not m or "Error" in (m.group(1) if m else ""):
        return {"status": "NOT_FOUND", "detail": f"arXiv {arxiv_id} not found"}
    ax_title = re.sub(r"\s+", " ", m.group(1)).strip()
    sim = similarity(entry.get("title", ""), ax_title)
    detail = {"arxiv_title": ax_title, "title_similarity": round(sim, 3)}
    if sim < 0.75:
        return {"status": "MISMATCH",
                "problems": [f"title mismatch (sim={sim:.2f}): arXiv='{ax_title[:90]}'"],
                **detail}
    return {"status": "OK", **detail}


def main() -> None:
    entries = parse_bib(BIB.read_text(encoding="utf-8"))
    report = {}
    counts = {"OK": 0, "MISMATCH": 0, "NOT_FOUND": 0, "UNCHECKED": 0, "ERROR": 0}
    for e in entries:
        key = e["key"]
        try:
            if "doi" in e:
                res = check_crossref(e)
            elif "eprint" in e:
                res = check_arxiv(e)
            else:
                res = {"status": "UNCHECKED",
                       "detail": f"no DOI/eprint ({e['type']}: {e.get('title', '')[:60]})"}
        except Exception as exc:  # network errors etc.
            res = {"status": "ERROR", "detail": str(exc)}
        report[key] = res
        counts[res["status"]] += 1
        flag = {"OK": " ", "UNCHECKED": "-"}.get(res["status"], "!")
        print(f"[{flag}] {res['status']:<9} {key}")
        for p in res.get("problems", []):
            print(f"      -> {p}")
        if res["status"] in ("NOT_FOUND", "ERROR"):
            print(f"      -> {res.get('detail', '')}")
        time.sleep(0.4)

    print("\nSummary:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    Path("/tmp/refs_validation.json").write_text(json.dumps(report, indent=2))
    print("Full report: /tmp/refs_validation.json")


if __name__ == "__main__":
    main()
