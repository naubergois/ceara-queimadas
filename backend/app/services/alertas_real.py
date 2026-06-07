"""
Gera alertas operacionais a partir de focos NASA FIRMS e clima Open-Meteo (sem banco).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

NIVEL_RANK = {"informativo": 0, "atencao": 1, "alerta": 2, "emergencia": 3}


def _id_alerta(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()[:32]


def _parse_dt(iso: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _recomendacao_foco(nivel: str, municipio: str) -> str:
    if nivel == "emergencia":
        return (
            f"AÇÃO IMEDIATA em {municipio}: acionar Defesa Civil e Corpo de Bombeiros. "
            "Monitorar focos críticos NASA FIRMS a cada 30 minutos."
        )
    if nivel == "alerta":
        return (
            f"Intensificar monitoramento em {municipio}. "
            "Enviar equipe de campo e verificar acesso viário às áreas com focos."
        )
    if nivel == "atencao":
        return f"Manter vigilância em {municipio}. Condições favorecem propagação de focos."
    return f"Acompanhar detecções em {municipio}. Sem ação imediata necessária."


def _recomendacao_clima(municipio: str) -> str:
    return (
        f"Risco meteorológico elevado em {municipio}: reforçar prevenção, "
        "restringir queimadas controladas e orientar comunidades rurais."
    )


def _nivel_por_focos(critica: int, alta: int, media: int, total: int) -> Optional[str]:
    if critica >= 3 or (critica >= 1 and alta >= 2):
        return "emergencia"
    if critica >= 1 or alta >= 2:
        return "alerta"
    if alta >= 1 or media >= 3 or total >= 5:
        return "atencao"
    if total >= 1:
        return "informativo"
    return None


def _nivel_por_clima(m: dict) -> Optional[str]:
    temp = m.get("temperatura_c") or 0
    umid = m.get("umidade_relativa") or 100
    vento = m.get("velocidade_vento_ms") or 0
    seca = m.get("dias_sem_chuva") or 0

    if seca >= 15 and umid < 30 and vento >= 7:
        return "emergencia"
    if temp >= 35 and seca >= 7:
        return "alerta"
    if seca >= 10 and umid < 40:
        return "atencao"
    if seca >= 7 and umid < 50:
        return "informativo"
    return None


def _mensagem_focos(municipio: str, critica: int, alta: int, media: int, total: int, frp_max: float) -> str:
    partes = [
        f"{total} foco(s) NASA FIRMS em {municipio} nas últimas 48h",
        f"({critica} críticos, {alta} altos, {media} médios)",
    ]
    if frp_max > 0:
        partes.append(f"FRP máximo: {frp_max:.1f} MW")
    return ". ".join(partes) + "."


def _mensagem_clima(municipio: str, m: dict) -> str:
    return (
        f"Condições de risco em {municipio}: "
        f"temp {m.get('temperatura_c', '—')}°C, "
        f"umidade {m.get('umidade_relativa', '—')}%, "
        f"{m.get('dias_sem_chuva', 0)} dias sem chuva significativa, "
        f"vento {m.get('velocidade_vento_ms', '—')} m/s."
    )


def gerar_alertas_reais(
    focos: list[dict],
    clima: list[dict],
    horas: int = 48,
) -> list[dict]:
    """
    Consolida alertas por município a partir de focos FIRMS e leituras Open-Meteo.
    """
    agora = datetime.now(timezone.utc)
    limite = agora - timedelta(hours=horas)
    por_municipio: dict[str, dict] = {}

    # --- Alertas por agregação de focos ---
    grupos: dict[str, list[dict]] = defaultdict(list)
    for f in focos:
        dt = _parse_dt(f.get("data_hora", ""))
        if dt and dt < limite:
            continue
        mun = (f.get("municipio") or "").strip() or "Área sem município identificado"
        grupos[mun].append(f)

    for municipio, lista in grupos.items():
        critica = sum(1 for f in lista if f.get("severidade") == "critica")
        alta = sum(1 for f in lista if f.get("severidade") == "alta")
        media = sum(1 for f in lista if f.get("severidade") == "media")
        total = len(lista)
        nivel = _nivel_por_focos(critica, alta, media, total)
        if not nivel:
            continue

        frp_vals = [f.get("frp") or 0 for f in lista]
        frp_max = max(frp_vals) if frp_vals else 0
        confs = [f.get("confianca") or 60 for f in lista]
        confianca = min(0.95, sum(confs) / len(confs) / 100)

        chave = f"focos|{municipio}"
        por_municipio[municipio] = {
            "id_alerta": _id_alerta(chave),
            "nivel": nivel,
            "municipio": municipio,
            "mensagem": _mensagem_focos(municipio, critica, alta, media, total, frp_max),
            "recomendacao": _recomendacao_foco(nivel, municipio),
            "data_hora": agora.isoformat(),
            "nivel_confianca": round(confianca, 2),
            "auditado": nivel in ("alerta", "emergencia"),
            "_rank": NIVEL_RANK[nivel],
        }

    # --- Alertas meteorológicos (complementam ou elevam nível) ---
    for m in clima:
        municipio = (m.get("nome") or "").strip()
        if not municipio:
            continue
        nivel_cli = _nivel_por_clima(m)
        if not nivel_cli:
            continue

        existente = por_municipio.get(municipio)
        if existente and NIVEL_RANK.get(existente["nivel"], 0) >= NIVEL_RANK[nivel_cli]:
            # reforça mensagem se já há alerta de foco
            if nivel_cli in ("alerta", "emergencia") and "clima" not in existente.get("mensagem", ""):
                existente["mensagem"] += " " + _mensagem_clima(municipio, m)
            continue

        chave = f"clima|{municipio}"
        por_municipio[municipio] = {
            "id_alerta": _id_alerta(chave),
            "nivel": nivel_cli,
            "municipio": municipio,
            "mensagem": _mensagem_clima(municipio, m),
            "recomendacao": _recomendacao_clima(municipio),
            "data_hora": agora.isoformat(),
            "nivel_confianca": 0.75 if nivel_cli == "informativo" else 0.85,
            "auditado": False,
            "_rank": NIVEL_RANK[nivel_cli],
        }

    alertas = list(por_municipio.values())
    alertas.sort(key=lambda a: (-a.pop("_rank", 0), a["municipio"]))
    return alertas
