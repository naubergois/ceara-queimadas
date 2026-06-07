import csv, io, requests
url = 'https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/focos_diario_br_20260604.csv'
resp = requests.get(url, timeout=30)
for enc in ['latin-1', 'utf-8']:
    reader = csv.DictReader(io.StringIO(resp.content.decode(enc)))
    for i, row in enumerate(reader):
        estado = (row.get('estado') or '').strip().upper()
        if 'CEAR' in estado or estado == 'CE' or 'CEARA' in estado:
            print(f'{enc} ROW {i}: estado={repr(estado)} municipio={repr(row.get("municipio",""))} bioma={repr(row.get("bioma",""))}')
