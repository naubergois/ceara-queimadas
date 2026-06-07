#!/usr/bin/env python3
import csv, io, requests, sys

url = 'https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/focos_diario_br_20260604.csv'
resp = requests.get(url, timeout=30)

# Checar conteudo raw
raw = resp.content
print("Content-Length:", len(raw))
print("Raw bytes starts with:", raw[:200])
print("Contains 'CEAR' bytes:", b'CEAR' in raw)

# Decode como latin-1
content_l1 = raw.decode('latin-1')
print("\n--- latin-1 decode, first 5 lines ---")
for line in content_l1.split('\n')[:5]:
    print(repr(line))

# csv com latin-1
reader = csv.DictReader(io.StringIO(content_l1))
count = 0
ce_count = 0
for row in reader:
    estado = (row.get('estado') or '').strip().upper()
    if count < 5:
        print(f"ROW {count}: estado={repr(estado)}, municipio={repr(row.get('municipio',''))}")
    if 'CE' == estado or 'CEAR' in estado or 'CEARA' in estado:
        ce_count += 1
    count += 1
print(f"\nTotal rows: {count}")
print(f"CE matches (latin-1): {ce_count}")

# Agora decode UTF-8
content_utf8 = raw.decode('utf-8')
reader2 = csv.DictReader(io.StringIO(content_utf8))
count2 = 0
ce_count2 = 0
for row in reader2:
    estado = (row.get('estado') or '').strip().upper()
    if count2 < 5:
        print(f"UTF8 ROW {count2}: estado={repr(estado)}")
    if 'CE' == estado or 'CEAR' in estado or 'CEARA' in estado:
        ce_count2 += 1
    count2 += 1
print(f"\nTotal rows (utf8): {count2}")
print(f"CE matches (utf8): {ce_count2}")
