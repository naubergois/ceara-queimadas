#!/usr/bin/env python3
"""Testa a coleta FIRMS via API oficial (requer MAP_KEY configurada)"""
import os, sys, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from app.core.config import settings
from app.services.firms_real import FIRMS_MAP_KEY, _coletar_focos_via_api

async def test():
    print("=== Testando coleta FIRMS via API oficial ===")
    
    if not FIRMS_MAP_KEY:
        print("❌ FIRMS MAP_KEY não configurada.")
        print("   Execute: ./scripts/setup_firms_key.sh SUA_CHAVE")
        print("   Para obter chave: https://firms.modaps.eosdis.nasa.gov/api/map_key/")
        return
    
    print(f"✅ MAP_KEY configurada (tamanho: {len(FIRMS_MAP_KEY)})")
    
    focos = await _coletar_focos_via_api(dias=1)
    print(f"Focos coletados via API (último 1 dia): {len(focos)}")
    
    if focos:
        print(f"Primeiro foco: {focos[0]}")
        sensores = set(f['sensor'] for f in focos)
        print(f"Sensores: {sensores}")
    
    print("\n✅ Teste concluído")

asyncio.run(test())
