#!/usr/bin/env python3
import re
with open('/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/artigo-queimadas-gemeo-digital.tex') as f:
    text = f.read()
bibitems = re.findall(r'\\bibitem\{([^}]+)\}', text)
cites_found = re.findall(r'\\cite\{([^}]+)\}', text)
used_keys = set()
for c in cites_found:
    for k in c.split(','):
        used_keys.add(k.strip())
bib_set = set(bibitems)
cited = bib_set & used_keys
uncited = bib_set - used_keys
print(f"Total bibitems: {len(bibitems)}")
print(f"Cited keys in text: {len(cited)}")
print(f"Uncited bibitems: {len(uncited)}")
if uncited:
    print("NOT CITED:")
    for u in sorted(uncited):
        print(f"  {u}")
