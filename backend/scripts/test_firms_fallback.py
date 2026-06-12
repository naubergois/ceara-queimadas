#!/usr/bin/env python3
"""Testa a coleta FIRMS via CSV público (fallback sem chave)"""
import os, sys, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from app.services.firms_real import _coletar_focos_csv_publico

async def test():
    print("=== Testando coleta FIRMS via CSV público (fallback) ===")
    focos = await _coletar_focos_csv_publico(dias=1)
    print(f"Focos coletados (último 1 dia): {len(focos)}")
    if focos:
        print(f"Primeiro foco: {focos[0]}")
        print(f"Último foco: {focos[-1]}")
        sensores = set(f['sensor'] for f in focos)
        print(f"Sensores detectados: {sensores}")
        severidades = {}
        for f in focos:
            s = f.get('severidade', 'desconhecida')
            severidades[s] = severidades.get(s, 0) + 1
        print(f"Distribuição de severidade: {severidades}")
    print("\n✅ Teste concluído")

asyncio.run(test())
