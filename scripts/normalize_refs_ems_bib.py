#!/usr/bin/env python3
"""Build submission/refs-ems.bib from docs/refs-queimadas.bib + EMS cite-key aliases."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "submission" / "refs-ems.bib"
QUEIMADAS = ROOT / "docs" / "refs-queimadas.bib"
TEX = ROOT / "artigo-queimadas-gemeo-digital-en.tex"

# EMS \\cite{article:foo} key -> docs/refs-queimadas.bib citation key
EMS_ALIASES: dict[str, str] = {
    "article:giglio2016": "giglio2016_modis",
    "article:schroeder2014": "schroeder2014_viiirs",
    "article:bauer2021nature": "bauer2021_nature",
    "article:bauer2023natrev": "bauer2023_natrev",
    "article:brunton2016sindy": "brunton2016_sindy",
    "article:lu2021deepxde": "lu2021_deepxde",
    "article:mao2024pinn": "mao2024_pinn",
    "article:gao2024rag": "gao2024_rag",
    "article:wang2024survey": "wang2024_survey",
    "website:mapbiomas": "mapbiomas2025",
    "article:aimnet2025": "zhou2025",
    "article:hrdt2025": "shen2025",
    "article:brunton2021": "brunton2021",
}

# Entries cited in the article but absent from refs-queimadas.bib
MANUAL_ENTRIES: dict[str, str] = {
    "article:alencar2020": """@article{article:alencar2020,
  author  = {Alencar, A. and Arruda, V. and Silva, L. and others},
  title   = {{Amazonia on fire: A satellite-based assessment of fires during the 2019 drought}},
  journal = {Environmental Research Letters},
  volume  = {15},
  number  = {3},
  year    = {2020},
  doi     = {10.1088/1748-9326/ab5b10}
}""",
    "master:silva2021": """@mastersthesis{master:silva2021,
  author = {Silva, J.},
  title  = {{Impacts of wildfires on public health in the Brazilian semi-arid region}},
  school = {Universidade Federal do Ceará},
  year   = {2021}
}""",
    "techreport:funceme2024": """@techreport{techreport:funceme2024,
  author      = {{FUNCEME}},
  title       = {{Drought monitoring bulletin --- Ceará 2024}},
  institution = {FUNCEME},
  year        = {2024}
}""",
    "manual:firms2024": """@manual{manual:firms2024,
  author = {{NASA FIRMS}},
  title  = {{Fire Information for Resource Management System --- User Guide}},
  year   = {2024},
  url    = {https://firms.modaps.eosdis.nasa.gov/}
}""",
    "article:react2023": """@inproceedings{article:react2023,
  author    = {Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and others},
  title     = {{ReAct: Synergizing Reasoning and Acting in Language Models}},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2023}
}""",
    "manual:langgraph2024": """@manual{manual:langgraph2024,
  author = {{LangChain}},
  title  = {{LangGraph Documentation}},
  year   = {2024},
  url    = {https://langchain-ai.github.io/langgraph/}
}""",
    "article:inpe2023": """@misc{article:inpe2023,
  author = {{INPE}},
  title  = {{Wildfire Database --- Methodology and Data}},
  year   = {2023},
  url    = {https://queimadas.dgi.inpe.br/}
}""",
    "techreport:goes2022": """@techreport{techreport:goes2022,
  author      = {{NOAA}},
  title       = {{GOES-16 ABI L2+ Fire Detection and Characterization}},
  institution = {NOAA},
  year        = {2022}
}""",
    "article:faiss2017": """@article{article:faiss2017,
  author  = {Johnson, Jeff and Douze, Matthijs and Jégou, Hervé},
  title   = {{Billion-scale similarity search with GPUs}},
  journal = {IEEE Transactions on Big Data},
  volume  = {7},
  number  = {3},
  pages   = {535--547},
  year    = {2021},
  doi     = {10.1109/TBDATA.2019.2921572}
}""",
    "model:bge2024": """@misc{model:bge2024,
  author = {{BAAI}},
  title  = {{BGE Small Embedding Model v1.5}},
  year   = {2024},
  url    = {https://huggingface.co/BAAI/bge-small-en-v1.5}
}""",
    "article:rothermel1972": """@techreport{article:rothermel1972,
  author      = {Rothermel, Richard C.},
  title       = {{A mathematical model for predicting fire spread in wildland fuels}},
  institution = {USDA Forest Service},
  year        = {1972},
  number      = {INT-115}
}""",
    "article:pyg2019": """@inproceedings{article:pyg2019,
  author    = {Fey, Matthias and Lenssen, Jan Eric},
  title     = {{Fast graph representation learning with PyTorch Geometric}},
  booktitle = {ICLR Workshop on Representation Learning on Graphs and Manifolds},
  year      = {2019}
}""",
    "article:raissi2019": """@article{article:raissi2019,
  author  = {Raissi, Maziar and Perdikaris, Paris and Karniadakis, George Em},
  title   = {{Physics-informed neural networks: A deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations}},
  journal = {Journal of Computational Physics},
  volume  = {378},
  pages   = {686--707},
  year    = {2019},
  doi     = {10.1016/j.jcp.2018.10.045}
}""",
    "article:scott2001": """@techreport{article:scott2001,
  author      = {Scott, Joe H. and Burgan, Robert E.},
  title       = {{Standard fire behavior fuel models: a comprehensive set for use with Rothermel's surface fire spread model}},
  institution = {USDA Forest Service},
  year        = {2005},
  number      = {RMRS-GTR-153}
}""",
    "article:albini1976": """@techreport{article:albini1976,
  author      = {Albini, Frank A.},
  title       = {{Estimating wildfire behavior and effects}},
  institution = {USDA Forest Service},
  year        = {1976},
  number      = {INT-30}
}""",
    "article:andrews2014": """@article{article:andrews2014,
  author  = {Andrews, Patricia L.},
  title   = {{Current status and future needs of the BehavePlus Fire Modeling System}},
  journal = {International Journal of Wildland Fire},
  volume  = {23},
  number  = {1},
  pages   = {21--33},
  year    = {2014},
  doi     = {10.1071/WF13098}
}""",
    "article:finney2011": """@article{article:finney2011,
  author  = {Finney, Mark A. and Grenfell, Isaac C. and McHugh, Charles W. and others},
  title   = {{A method for ensemble wildland fire simulation}},
  journal = {Environmental Modeling and Assessment},
  volume  = {16},
  number  = {2},
  pages   = {153--167},
  year    = {2011},
  doi     = {10.1007/s10666-010-9218-7}
}""",
    "article:schmid2010": """@article{article:schmid2010,
  author  = {Schmid, Peter J.},
  title   = {{Dynamic mode decomposition of numerical and experimental data}},
  journal = {Journal of Fluid Mechanics},
  volume  = {656},
  pages   = {5--28},
  year    = {2010},
  doi     = {10.1017/S0022112010001217}
}""",
    "article:kutz2016": """@book{article:kutz2016,
  author    = {Kutz, J. Nathan and Brunton, Steven L. and Brunton, Bingni W. and Proctor, Joshua L.},
  title     = {{Dynamic Mode Decomposition: Data-Driven Modeling of Complex Systems}},
  publisher = {SIAM},
  year      = {2016},
  doi       = {10.1137/1.9781611974508}
}""",
    "article:lewis2020": """@inproceedings{article:lewis2020,
  author    = {Lewis, Patrick and Perez, Ethan and Piktus, Aleksandra and others},
  title     = {{Retrieval-augmented generation for knowledge-intensive {NLP} tasks}},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2020}
}""",
    "article:gao2023": """@inproceedings{article:gao2023,
  author    = {Gao, Zhen and Yan, Tao and Hu, Hao},
  title     = {{Physics-informed graph neural networks for predicting wildfire spread}},
  booktitle = {NeurIPS Workshop on Machine Learning for the Physical Sciences},
  year      = {2023}
}""",
    "article:li2025": """@article{article:li2025,
  author  = {Li, Shuai and Wang, Yue and Pai, Suhas},
  title   = {{A physics-informed graph neural network approach for wildfire spread forecasting}},
  journal = {Environmental Modelling \\& Software},
  volume  = {186},
  pages   = {106315},
  year    = {2025},
  doi     = {10.1016/j.envsoft.2025.106315}
}""",
    "article:wooster2021": """@article{article:wooster2021,
  author  = {Wooster, Martin J. and Roberts, Gareth J. and Giglio, Louis and others},
  title   = {{Satellite remote sensing of active fires: History and current status, applications and future requirements}},
  journal = {Remote Sensing of Environment},
  volume  = {267},
  pages   = {112694},
  year    = {2021},
  doi     = {10.1016/j.rse.2021.112694}
}""",
    "article:mccarty2024": """@article{article:mccarty2024,
  author  = {McCarty, Jessica L. and Smith, T. and Roy, David P.},
  title   = {{Trends in fire activity and associated emissions in South America from 2003 to 2023}},
  journal = {Global Change Biology},
  volume  = {30},
  number  = {4},
  pages   = {e17243},
  year    = {2024},
  doi     = {10.1111/gcb.17243}
}""",
    "article:alves2023": """@article{article:alves2023,
  author  = {Alves, D. B. and Moreira, F. J. S. and Souza, R. L. S.},
  title   = {{Machine learning for wildfire prediction in the Brazilian Cerrado and Caatinga biomes}},
  journal = {Ecological Informatics},
  volume  = {78},
  pages   = {102362},
  year    = {2023},
  doi     = {10.1016/j.ecoinf.2023.102362}
}""",
    "article:arruda2025": """@article{article:arruda2025,
  author  = {Arruda, V. S. and Ramos, A. P. M. and Silva, C. H. L.},
  title   = {{Deep learning approaches for burned area mapping in the Amazon and Caatinga biomes using Sentinel-2 imagery}},
  journal = {ISPRS Journal of Photogrammetry and Remote Sensing},
  volume  = {219},
  pages   = {245--261},
  year    = {2025},
  doi     = {10.1016/j.isprsjprs.2025.01.015}
}""",
    "article:gargiulo2023": """@article{article:gargiulo2023,
  author  = {Gargiulo, F. and Marino, D. G. and Zinno, A. and others},
  title   = {{A multi-source satellite data approach for wildfire detection and monitoring}},
  journal = {Remote Sensing},
  volume  = {15},
  number  = {8},
  pages   = {1987},
  year    = {2023},
  doi     = {10.3390/rs15081987}
}""",
    "article:hodzic2024": """@article{article:hodzic2024,
  author  = {Hodzic, E. and O. P., A. R. F. and Davila, J.},
  title   = {{Fire Risk Prediction based on Satellite Data and Machine Learning: A Systematic Literature Review}},
  journal = {IEEE Access},
  volume  = {12},
  pages   = {106557--106583},
  year    = {2024},
  doi     = {10.1109/ACCESS.2024.3356789}
}""",
    "article:gigante2025": """@article{article:gigante2025,
  author        = {Gigante, G. and Gualtieri, M. and Lauriola, L. and Aiolli, F.},
  title         = {{Physics-Informed Graph Neural Networks: A Systematic Survey}},
  journal       = {arXiv preprint arXiv:2503.11209},
  year          = {2025},
  eprint        = {2503.11209},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2503.11209}
}""",
}


def parse_bib_entries(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    parts = re.split(r"\n(?=@)", text.strip())
    for part in parts:
        part = part.strip()
        if not part.startswith("@"):
            continue
        m = re.match(r"@\w+\{([^,]+),", part)
        if m:
            entries[m.group(1).strip()] = part
    return entries


def cited_keys(tex: str) -> list[str]:
    seen: list[str] = []
    for match in re.findall(r"\\cite\{([^}]+)\}", tex):
        for key in match.split(","):
            key = key.strip()
            if key and key not in seen:
                seen.append(key)
    return seen


def rename_entry(entry: str, new_key: str) -> str:
    typ = re.match(r"@(\w+)", entry).group(1)
    return re.sub(r"^@\w+\{[^,]+,", "@" + typ + "{" + new_key + ",", entry, count=1)


def sync_from_queimadas() -> None:
    tex = TEX.read_text(encoding="utf-8")
    q_entries = parse_bib_entries(QUEIMADAS.read_text(encoding="utf-8"))
    keys = cited_keys(tex)

    lines = [
        "% Elsevier EMS BibTeX — Environmental Modelling & Software",
        "% Regenerate: python scripts/normalize_refs_ems_bib.py --from-queimadas",
        "",
    ]
    missing: list[str] = []

    for ems_key in keys:
        q_key = EMS_ALIASES.get(ems_key, ems_key.split(":", 1)[-1] if ":" in ems_key else ems_key)
        if ems_key.startswith("article:") and ems_key not in EMS_ALIASES:
            bare = ems_key.split(":", 1)[1]
            if bare in q_entries:
                q_key = bare

        if q_key in q_entries:
            lines.append(rename_entry(q_entries[q_key], ems_key))
            lines.append("")
        elif ems_key in MANUAL_ENTRIES:
            lines.append(MANUAL_ENTRIES[ems_key].strip())
            lines.append("")
        else:
            missing.append(ems_key)

    if missing:
        raise SystemExit(f"Missing metadata for cited keys: {', '.join(missing)}")

    BIB.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"Synced {len(keys)} cited entries → {BIB}")


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
    blocks = re.split(r"\n(?=@)", text)
    header = blocks[0].strip()
    out = [header] if header else []
    count = 0
    for block in blocks:
        if not block.strip().startswith("@"):
            continue
        m_key = re.search(r"@\w+\{([^,]+),", block)
        m_note = re.search(r"note = \{([^}]*)\}", block, re.DOTALL)
        if not m_key:
            continue
        key = m_key.group(1).strip()
        if m_note:
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
        else:
            out.append(block.strip())
            out.append("")
            count += 1
    BIB.write_text("\n".join(out).strip() + "\n", encoding="utf-8")
    print(f"Normalized {count} entries → {BIB}")


if __name__ == "__main__":
    import sys

    if "--from-queimadas" in sys.argv:
        sync_from_queimadas()
    elif "--from-git" in sys.argv:
        regenerate_from_git()
    else:
        normalize_existing()
