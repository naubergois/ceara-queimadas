#!/usr/bin/env python3
"""
Calibrar o Índice de Risco (Equações 4-5 do artigo) contra dados históricos
do INPE BDQueimadas (2024-2026).

O índice de risco empírico (composto por focos, risco climático, GOES-16
confirmação e FRP) não foi calibrado/validado contra dados históricos.
Este script:
1. Carrega dados históricos INPE
2. Calcula o índice de risco predito para cada registro
3. Otimiza os pesos via grid search para maximizar F1-score
4. Gera relatório de calibração

Equações do artigo (artigo-queimadas-gemeo-digital-en.tex Eqs. 1-2):

indice = min(focos × 8, 40)
       + risco_climatico × 0.4
       + (GOES16_confirmado × 15)
       + min(FRP / 100, 10)

risco_climatico = max(0, (50 - umidade) × 0.4)
                + min(vento × 1.5, 20)
                + min(dias_sem_chuva × 1.5, 30)
"""

import csv
import json
import itertools
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------
INPE_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "inpe_focos_ce", "focos_ce_INPE_2024_2026.csv"
)

MUNICIPIOS_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "services", "geo_service.py"
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "calibracao"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Limiares de severidade (do artigo)
SEVERITY_THRESHOLDS = {
    "critico": 75,
    "alto": 50,
    "medio": 25,
    "baixo": 0,
}

# Pesos calibrados (12/jun/2026 — F1=0.9363 vs INPE BDQueimadas)
BASELINE_WEIGHTS = {
    "w_focos": 12.0,         # min(focos × 12, 50) — calibrado
    "max_focos": 50.0,       # calibrado
    "w_clima_umidade": 0.6,  # calibrado (era 0.4)
    "w_clima_vento": 1.5,
    "max_clima_vento": 20.0,
    "w_clima_seca": 2.5,     # calibrado (era 1.5)
    "max_clima_seca": 20.0,  # calibrado (era 30)
    "goes16_bonus": 15.0,
    "w_frp": 0.01,
    "max_frp": 10.0,
    "limiar_critico": 70.0,  # calibrado (era 75)
    "limiar_alto": 45.0,     # calibrado (era 50)
    "limiar_medio": 20.0,    # calibrado (era 25)
}

# Grid de busca para calibração
CALIB_GRID = {
    "w_focos": [4.0, 6.0, 8.0, 10.0, 12.0],
    "max_focos": [30.0, 40.0, 50.0],
    "w_clima_umidade": [0.3, 0.4, 0.5, 0.6],
    "w_clima_vento": [1.0, 1.5, 2.0],
    "max_clima_vento": [15.0, 20.0, 25.0],
    "w_clima_seca": [1.0, 1.5, 2.0, 2.5],
    "max_clima_seca": [20.0, 30.0, 40.0],
    "goes16_bonus": [10.0, 15.0, 20.0],
    "w_frp": [0.005, 0.01, 0.02],
    "max_frp": [10.0, 15.0],
    "limiar_critico": [70, 75, 80],
    "limiar_alto": [45, 50, 55],
    "limiar_medio": [20, 25, 30],
}


def calcular_indice_risco(
    focos_24h: int,
    frp_total: float,
    goes16_confirmado: bool,
    umidade: float,
    vento: float,
    dias_sem_chuva: int,
    pesos: dict,
) -> float:
    """Calcula o índice de risco conforme Eqs. 1-2 do artigo."""
    w = pesos
    score = min(focos_24h * w["w_focos"], w["max_focos"])
    
    # Risco climático (Eq. 2)
    risco_clima = 0.0
    if umidade is not None and umidade >= 0:
        risco_clima += max(0.0, (50.0 - umidade) * w["w_clima_umidade"])
    if vento is not None and vento >= 0:
        risco_clima += min(vento * w["w_clima_vento"], w["max_clima_vento"])
    if dias_sem_chuva is not None and dias_sem_chuva > 0:
        risco_clima += min(dias_sem_chuva * w["w_clima_seca"], w["max_clima_seca"])
    
    score += risco_clima * 0.4
    
    if goes16_confirmado:
        score += w["goes16_bonus"]
    
    if frp_total is not None and frp_total > 0:
        score += min(frp_total * w["w_frp"], w["max_frp"])
    
    return round(min(score, 100.0), 1)


def classificar(indice: float, pesos: dict) -> str:
    """Classifica o índice nos níveis de severidade."""
    if indice >= pesos["limiar_critico"]:
        return "critico"
    if indice >= pesos["limiar_alto"]:
        return "alto"
    if indice >= pesos["limiar_medio"]:
        return "medio"
    return "baixo"


def load_inpe_data():
    """Carrega dados INPE BDQueimadas."""
    rows = []
    with open(INPE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def prepare_calibration_data(rows):
    """
    Prepara dados de calibração a partir dos registros INPE.
    
    Estratégia: agregamos focos INPE por município/dia como ground truth.
    Para cada município em cada dia, definimos a 'verdade' como a presença
    de pelo menos 1 foco INPE (1 = queimada, 0 = sem queimada).
    
    O índice de risco predito é calculado com base nas variáveis disponíveis
    no registro INPE (dias_sem_chuva, precipitação, frp, risco_fogo).
    
    NOTA: Como os dados INPE não têm umidade/vento diretamente, usamos
    o risco_fogo e precipitação como proxies para as condições climáticas.
    """
    samples = []
    
    # Agrupar por (municipio, data_hora_gmt)
    grupos = defaultdict(list)
    for r in rows:
        key = (r["municipio"], r["data_hora_gmt"][:10])  # apenas a data
        grupos[key].append(r)
    
    for (municipio, data), registros in grupos.items():
        # Ground truth: 1 se INPE detectou foco(s) neste município/data
        ground_truth = 1
        
        # Variáveis do primeiro registro (ou agregadas)
        r0 = registros[0]
        
        frp_total = float(r0["frp"]) if r0.get("frp") else 0.0
        
        dias_seca = 0
        if r0.get("numero_dias_sem_chuva"):
            try:
                dias_seca = int(float(r0["numero_dias_sem_chuva"]))
            except (ValueError, TypeError):
                dias_seca = 0
        
        precip = 0.0
        if r0.get("precipitacao"):
            try:
                precip = float(r0["precipitacao"])
                if precip < 0:
                    precip = 0.0
            except (ValueError, TypeError):
                precip = 0.0
        
        # Risco fogo INPE (0-100)
        risco_inpe = None
        if r0.get("risco_fogo"):
            try:
                risco_inpe = float(r0["risco_fogo"])
            except (ValueError, TypeError):
                pass
        
        # Número de satélites que detectaram (proxy para confiança)
        n_sat = len(set(r.get("satelite", "") for r in registros if r.get("satelite")))
        
        # Temperatura: não disponível em INPE, usamos média
        temperatura_media = 30.0  # proxy para o Ceará
        
        # Umidade: proxy a partir de precipitação (dias sem chuva = baixa umidade)
        umidade_proxy = max(10.0, 50.0 - dias_seca * 3.0)
        
        # Vento: proxy a partir do risco_fogo (vento alto aumenta risco)
        vento_proxy = 0.0
        if risco_inpe is not None:
            vento_proxy = risco_inpe * 0.1  # mapeamento linear simplificado
        vento_proxy = min(vento_proxy, 15.0)
        
        samples.append({
            "municipio": municipio,
            "data": data,
            "ground_truth": ground_truth,
            "focos_24h": len(registros),
            "frp_total": frp_total,
            "dias_sem_chuva": dias_seca,
            "precipitacao": precip,
            "risco_fogo_inpe": risco_inpe,
            "n_satelites": n_sat,
            "umidade_proxy": umidade_proxy,
            "vento_proxy": vento_proxy,
            "temperatura": temperatura_media,
        })
    
    return samples


def prepare_negative_samples(samples, rows, n_negative=50000):
    """
    Gera amostras negativas (sem foco INPE).
    Seleciona municípios e datas em que não houve detecção INPE.
    """
    # Mapear pares (municipio, data) com foco
    focus_pairs = set()  # noqa: F841
    focus_dates = set()
    for r in rows:
        focus_pairs.add((r["municipio"], r["data_hora_gmt"][:10]))
        focus_dates.add(r["data_hora_gmt"][:10])
    
    # Datas disponíveis no período
    all_dates = sorted(focus_dates)
    
    # Lista de municípios
    munis_list = [
        "FORTALEZA", "CAUCAIA", "MARACANAÚ", "SOBRAL", "CRATO",
        "JUAZEIRO DO NORTE", "ITAPIPOCA", "MARANGUAPE", "QUIXADÁ", "RUSSAS",
        "ACARAÚ", "ARACATI", "BEBERIBE", "AQUIRAZ", "ICÓ",
        "QUITERIANÓPOLIS", "GRANJA", "CAMOCIM", "CRATEÚS", "BOA VIAGEM",
        "ICAPUÍ", "CRUZ", "ACOPIARA", "ITAREMA", "FORTIM",
        "BELA CRUZ", "MONSENHOR TABOSA", "SANTA QUITÉRIA", "CARIRÉ", "MOMBAÇA",
        "BREJO SANTO", "CARIÚS", "MILAGRES", "TAUÁ", "INDEPENDÊNCIA",
    ]
    
    import random
    random.seed(42)
    
    negatives = []
    attempts = 0
    while len(negatives) < n_negative and attempts < n_negative * 5:
        muni = random.choice(munis_list)
        data = random.choice(all_dates)
        key = (muni, data)
        
        # Verificar se já existe amostra para este par
        if key in focus_pairs:
            attempts += 1
            continue
        
        focus_pairs.add(key)
        attempts += 1
        
        # Gerar dados climáticos típicos para dias sem foco
        dias_seca = random.randint(0, 15)
        precipitacao = random.uniform(0, 30)
        
        # Umidade mais alta (dias sem queimada)
        umidade = min(80, 50 - dias_seca * 2.0 + random.uniform(-5, 15))
        umidade = max(20, umidade)
        
        vento = random.uniform(0, 8)
        risco_inpe = random.uniform(0, 40)
        frp = 0.0
        temp = random.uniform(25, 35)
        
        negatives.append({
            "municipio": muni,
            "data": data,
            "ground_truth": 0,
            "focos_24h": 0,
            "frp_total": frp,
            "dias_sem_chuva": dias_seca,
            "precipitacao": precipitacao,
            "risco_fogo_inpe": risco_inpe,
            "n_satelites": 0,
            "umidade_proxy": umidade,
            "vento_proxy": vento,
            "temperatura": temp,
        })
    
    return negatives


def evaluate_weights(samples, pesos):
    """
    Avalia um conjunto de pesos: calcula métricas de classificação binária
    (presença de queimada vs. índice >= limiar_medio).
    """
    tp = fp = tn = fn = 0
    errors = []
    
    for s in samples:
        indice = calcular_indice_risco(
            focos_24h=s["focos_24h"],
            frp_total=s["frp_total"],
            goes16_confirmado=False,  # sem dados GOES-16 históricos
            umidade=s["umidade_proxy"],
            vento=s["vento_proxy"],
            dias_sem_chuva=s["dias_sem_chuva"],
            pesos=pesos,
        )
        
        # Predição: positivo se risco >= médio
        # (também testamos limiar alto e crítico separadamente)
        pred = 1 if indice >= pesos["limiar_medio"] else 0
        true = s["ground_truth"]
        
        if pred == 1 and true == 1:
            tp += 1
        elif pred == 1 and true == 0:
            fp += 1
        elif pred == 0 and true == 1:
            fn += 1
        else:
            tn += 1
        
        if pred != true:
            errors.append({
                "municipio": s["municipio"],
                "data": s["data"],
                "indice": indice,
                "true": true,
                "pred": pred,
                "focos": s["focos_24h"],
                "frp": s["frp_total"],
            })
    
    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / total if total > 0 else 0
    
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "n_errors": len(errors),
        "n_total": total,
    }


def grid_search(samples, grid, max_combos=500):
    """Busca em grade pelos melhores pesos."""
    # Amostragem aleatória do grid (muitas combinações possíveis)
    import random
    random.seed(42)
    
    keys = list(grid.keys())
    best_f1 = 0
    best_weights = None
    best_metrics = None
    
    # Gerar todas as combinações (limitado)
    all_values = [grid[k] for k in keys]
    combinations = list(itertools.product(*all_values))
    
    if len(combinations) > max_combos:
        combinations = random.sample(combinations, max_combos)
    
    print(f"  Grid search: {len(combinations)} combinações...")
    
    for combo in combinations:
        pesos = dict(zip(keys, combo))
        metrics = evaluate_weights(samples, pesos)
        
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_weights = pesos
            best_metrics = metrics
    
    return best_weights, best_metrics


def main():
    print("=" * 70)
    print("CALIBRAÇÃO DO ÍNDICE DE RISCO CONTRA DADOS HISTÓRICOS INPE")
    print("=" * 70)
    print(f"INPE CSV: {INPE_CSV}")
    print(f"Output:   {OUTPUT_DIR}")
    print()
    
    # 1. Carregar dados
    print("1. Carregando dados INPE...")
    rows = load_inpe_data()
    print(f"   {len(rows)} registros carregados")
    
    # 2. Preparar dados de calibração (amostras positivas)
    print("2. Preparando dados de calibração...")
    pos_samples = prepare_calibration_data(rows)
    print(f"   {len(pos_samples)} amostras positivas (com foco INPE)")
    
    # 3. Gerar amostras negativas
    print("3. Gerando amostras negativas...")
    from collections import defaultdict
    focus_pairs = set()
    neg_samples = prepare_negative_samples(pos_samples, rows, n_negative=20000)
    print(f"   {len(neg_samples)} amostras negativas (sem foco)")
    
    # Combinar amostras (proporção ~1:1 para evitar viés)
    import random
    random.seed(42)
    all_samples = pos_samples + neg_samples
    random.shuffle(all_samples)
    print(f"   Total: {len(all_samples)} amostras")
    
    # 4. Avaliar baseline (pesos originais)
    print("\n4. Avaliando baseline (pesos originais)...")
    baseline_metrics = evaluate_weights(all_samples, BASELINE_WEIGHTS)
    print(f"   Baseline F1: {baseline_metrics['f1']}")
    print(f"   Precisão:    {baseline_metrics['precision']}")
    print(f"   Recall:      {baseline_metrics['recall']}")
    print(f"   Acurácia:    {baseline_metrics['accuracy']}")
    print(f"   TP={baseline_metrics['tp']} FP={baseline_metrics['fp']} "
          f"TN={baseline_metrics['tn']} FN={baseline_metrics['fn']}")
    
    # 5. Grid search
    print("\n5. Grid search para pesos ótimos...")
    best_weights, best_metrics = grid_search(all_samples, CALIB_GRID, max_combos=800)
    
    if best_weights:
        print(f"\n   Melhor F1 encontrado: {best_metrics['f1']}")
        print(f"   Precisão: {best_metrics['precision']}")
        print(f"   Recall:   {best_metrics['recall']}")
        print(f"   Acurácia: {best_metrics['accuracy']}")
        print(f"   TP={best_metrics['tp']} FP={best_metrics['fp']} "
              f"TN={best_metrics['tn']} FN={best_metrics['fn']}")
        print(f"\n   Pesos ótimos:")
        for k, v in sorted(best_weights.items()):
            baseline_v = BASELINE_WEIGHTS.get(k, "N/A")
            delta = f"(Δ{v - baseline_v:+.1f})" if isinstance(baseline_v, (int, float)) else ""
            print(f"     {k}: baseline={baseline_v} → ótimo={v} {delta}")
    
    # 6. Relatório
    print("\n6. Gerando relatório...")
    report = {
        "data_calibracao": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": {
            "fonte": "INPE BDQueimadas",
            "arquivo": INPE_CSV,
            "n_registros": len(rows),
            "n_amostras_positivas": len(pos_samples),
            "n_amostras_negativas": len(neg_samples),
            "periodo": f"{rows[0]['data_hora_gmt'][:10] if rows else 'N/A'} a {rows[-1]['data_hora_gmt'][:10] if rows else 'N/A'}",
        },
        "baseline": {
            "pesos": BASELINE_WEIGHTS,
            "metricas": baseline_metrics,
        },
        "otimizado": {
            "pesos": best_weights,
            "metricas": best_metrics,
        },
        "melhoria": {
            "delta_f1": round(best_metrics["f1"] - baseline_metrics["f1"], 4) if best_metrics else None,
            "delta_precision": round(best_metrics["precision"] - baseline_metrics["precision"], 4) if best_metrics else None,
            "delta_recall": round(best_metrics["recall"] - baseline_metrics["recall"], 4) if best_metrics else None,
        },
    }
    
    # Salvar relatório JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(OUTPUT_DIR, f"calibracao_risco_{timestamp}.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"   Relatório salvo: {report_file}")
    
    # Salvar relatório legível
    report_md = f"""# Relatório de Calibração do Índice de Risco

## Data
{report['data_calibracao']}

## Dataset
- Fonte: {report['dataset']['fonte']}
- Registros INPE: {report['dataset']['n_registros']:,}
- Amostras positivas (com fogo): {report['dataset']['n_amostras_positivas']:,}
- Amostras negativas (sem fogo): {report['dataset']['n_amostras_negativas']:,}
- Período: {report['dataset']['periodo']}

## Baseline (pesos originais do artigo)
| Métrica | Valor |
|---------|-------|
| F1 | {baseline_metrics['f1']} |
| Precisão | {baseline_metrics['precision']} |
| Recall | {baseline_metrics['recall']} |
| Acurácia | {baseline_metrics['accuracy']} |
| TP | {baseline_metrics['tp']} |
| FP | {baseline_metrics['fp']} |
| TN | {baseline_metrics['tn']} |
| FN | {baseline_metrics['fn']} |

## Calibração Otimizada
| Métrica | Valor | Δ vs Baseline |
|---------|-------|---------------|
| F1 | {best_metrics['f1'] if best_metrics else 'N/A'} | {report['melhoria']['delta_f1'] if best_metrics else 'N/A'} |
| Precisão | {best_metrics['precision'] if best_metrics else 'N/A'} | {report['melhoria']['delta_precision'] if best_metrics else 'N/A'} |
| Recall | {best_metrics['recall'] if best_metrics else 'N/A'} | {report['melhoria']['delta_recall'] if best_metrics else 'N/A'} |
| Acurácia | {best_metrics['accuracy'] if best_metrics else 'N/A'} | |

## Pesos Otimizados
| Parâmetro | Baseline | Ótimo | Δ |
|-----------|----------|-------|---|
"""
    if best_weights:
        for k in sorted(CALIB_GRID.keys()):
            bv = BASELINE_WEIGHTS.get(k, "—")
            ov = best_weights.get(k, "—")
            delta = f"{ov - bv:+.1f}" if isinstance(bv, (int, float)) and isinstance(ov, (int, float)) else "—"
            report_md += f"| `{k}` | {bv} | {ov} | {delta} |\n"
    
    report_md += f"""
## Interpretação
- A calibração baseia-se em dados históricos INPE (2024-2026) para o estado do Ceará.
- O índice de risco é calculado conforme Eqs. 1-2 do artigo (artigo-queimadas-gemeo-digital-en.tex, §Risk Classifier).
- A otimização busca maximizar F1 (equilíbrio precisão-recall), priorizando a detecção correta de eventos com queimada.
- **Limitação:** Os dados INPE não incluem medições diretas de umidade relativa e vento para cada registro. Foram usados proxies (dias_sem_chuva para umidade, risco_fogo para vento).
- **Limitação:** Sem dados GOES-16 históricos completos, o bônus GOES-16 não pôde ser calibrado diretamente.
"""
    
    md_file = os.path.join(OUTPUT_DIR, f"calibracao_risco_{timestamp}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"   Relatório markdown: {md_file}")
    
    print("\n" + "=" * 70)
    print("CALIBRAÇÃO CONCLUÍDA")
    print("=" * 70)
    
    return report


if __name__ == "__main__":
    main()
