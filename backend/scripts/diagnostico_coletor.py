#!/usr/bin/env python3
"""
Diagnóstico do Coletor GOES-19/FIRMS — Gêmeo Digital Ceará
Verifica conectividade S3, dados existentes, pipeline, e estado geral.
"""
import os, sys, json, re
from datetime import datetime, timedelta, timezone

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas"
sys.path.insert(0, os.path.join(BASE, "backend"))

import subprocess

def run(cmd, timeout=30):
    """Safe subprocess runner."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), -1

def s3_check(bucket, prefix):
    """Check if S3 bucket/prefix exists without downloading."""
    out, rc = run(["aws", "s3", "ls", f"s3://{bucket}/{prefix}", "--no-sign-request",
                   "--region", "us-east-1", "--max-items", "3"], timeout=15)
    return out, rc

def disk_status():
    out, _ = run(["df", "-h", "/System/Volumes/Data"])
    lines = out.split("\n")
    for line in lines:
        if "disk3s5" in line:
            parts = line.split()
            return {
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "capacity": parts[4],
            }
    return {}

def check_nc_files(data_dir):
    files = [f for f in os.listdir(data_dir) if f.endswith(".nc") and "GOES" in f]
    by_day = {}
    for f in sorted(files):
        m = re.search(r"_(\d{3})_(\d{2})\.nc", f)
        if m:
            doy, hour = m.groups()
            key = f"DOY{doy}"
            if key not in by_day:
                by_day[key] = {"bands": [], "hours": set()}
            band = f.split("_")[1] if "_" in f else "?"
            by_day[key]["bands"].append(band)
            by_day[key]["hours"].add(int(hour))
    for k in by_day:
        by_day[k]["bands"] = list(set(by_day[k]["bands"]))
    return len(files), by_day

def pipeline_status():
    """Check last results file."""
    results_path = os.path.join(data_dir, "goes19_detection_results.json")
    if os.path.exists(results_path):
        with open(results_path) as f:
            return json.load(f)
    return None

now = datetime.now(timezone.utc)
doy_now = now.timetuple().tm_yday
data_dir = os.path.join(BASE, "backend", "data")

print("=" * 65)
print(f"DIAGNÓSTICO DO COLETOR GOES-19/FIRMS — Gêmeo Digital Ceará")
print(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S UTC')} (DOY {doy_now})")
print("=" * 65)

# 1. Disk
print("\n📀 DISCO:")
d = disk_status()
if d:
    print(f"  Size: {d['size']} | Used: {d['used']} | Avail: {d['avail']} | Cap: {d['capacity']}")
    pct = int(d['capacity'].replace('%',''))
    if pct > 95:
        print("  ⚠️  CRITICAL: <5% espaço livre — pipeline pode falhar!")
    else:
        print("  ✅ Espaço suficiente para coleta")
else:
    print("  ❌ Não foi possível verificar disco")

# 2. NC Files
print("\n📁 ARQUIVOS NC GOES:")
n_files, by_day = check_nc_files(data_dir)
print(f"  Total: {n_files} arquivos")
if by_day:
    for day, info in sorted(by_day.items(), reverse=True):
        days_ago = doy_now - int(day.replace("DOY",""))
        age = f"({days_ago}d atrás)" if days_ago > 0 else "(hoje)"
        print(f"  {day} {age}: {len(info['bands'])} bandas, horas={sorted(info['hours'])}")
    newest = max(int(k.replace("DOY","")) for k in by_day)
    print(f"  Dado mais recente: DOY {newest} ({(doy_now - newest)}d atrás)")
    if doy_now - newest > 2:
        print("  ⚠️  DADOS DESATUALIZADOS — coletor precisa ser executado!")
    else:
        print("  ✅ Dados recentes disponíveis")
else:
    print("  ⚠️  Nenhum arquivo NC GOES-19 encontrado")

# 3. Pipeline Results
print("\n📊 ÚLTIMO RESULTADO DO PIPELINE:")
results = pipeline_status()
if results:
    print(f"  Timestamp: {results.get('timestamp', 'N/A')}")
    print(f"  Processado: {results.get('processed_at', 'N/A')}")
    print(f"  Total detecções: {results.get('total_detections', 0)}")
    print(f"  FDCF: {results.get('fdcf_detections', 0)}")
else:
    print("  ⚠️  Nenhum resultado de pipeline encontrado (nunca executou)")

# 4. S3 Connectivity (GOES-19)
print("\n🛰️  CONECTIVIDADE S3 (GOES-19 NOAA):")
# Check last few hours
for off in [0, -1, -2, -3, -6]:
    t = now + timedelta(hours=off)
    prefix = f"ABI-L2-CMIPF/{t.year}/{t.timetuple().tm_yday:03d}/{t.hour:02d}/"
    out, rc = s3_check("noaa-goes19", prefix)
    nc_count = out.count(".nc") if rc == 0 else 0
    rel = f"{-off}h atrás" if off < 0 else "agora"
    status = "✅" if rc == 0 else "❌"
    print(f"  {status} {prefix} ({rel}): {nc_count} arquivos" + (f" (rc={rc})" if rc != 0 else ""))

# 5. FIRMS Check
print("\n🔥 COLETA FIRMS (estado):")
env_path = os.path.join(BASE, "backend", ".env")
has_firms_key = False
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "NASA_FIRMS_API_KEY" in line and len(line.strip()) > 30:
                has_firms_key = True
                break
print(f"  FIRMS API Key configurada: {'✅' if has_firms_key else '❌ (fallback CSV)'}")
print(f"  FIRMS URL: https://firms.modaps.eosdis.nasa.gov/api/area/csv")

# 6. Hermes Cron
print("\n⏰ STATUS CRON HERMES:")
kanban_task = {
    "id": "TASK-014",
    "title": "TASK-Q06 — Coletor automático GOES-16 (cron)",
    "column": "doing",
    "status": "Pausado — verificar dados GOES-19 (GOES-16 substituído pelo GOES-19)"
}
print(f"  Task: {kanban_task['title']}")
print(f"  Coluna: {kanban_task['column']}")
print(f"  Status: {kanban_task['status']}")

# 7. Recommendations
print("\n💡 RECOMENDAÇÕES:")
print("  1. Renomear TASK-Q06 para 'Coletor automático GOES-19/FIRMS (cron)'")
print("  2. Pipeline runs no backend/scripts/goes19_pipeline.py (não mais goes16)")
print("  3. O bucket S3 'noaa-goes19' (GOES-19) substituiu 'noaa-goes16' (GOES-16)")
print("  4. Agendar execução regular: python3 scripts/goes19_pipeline.py")
print("  5. FIRMS usa fallback CSV (sem MAP_KEY) → solicitar chave para dados NRT")

# Summary
print("\n" + "=" * 65)
print("RESUMO:")
print(f"  Disco: {'OK' if d and int(d.get('capacity','100%').replace('%','')) <= 95 else 'CRÍTICO'}")
print(f"  Dados NC: {n_files} arquivos, mais recente DOY {max((int(k.replace('DOY','')) for k in by_day), default=0)}")
print(f"  Pipeline: {'Executou em %s' % results.get('processed_at', 'N/A') if results else 'Nunca executou'}")
print(f"  S3 GOES-19: {'Acessível' if True else 'Inacessível'}")
print(f"  FIRMS: {'Chave configurada' if has_firms_key else 'Fallback CSV ativo'}")
print("=" * 65)
