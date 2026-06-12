#!/usr/bin/env python3
"""Testa a configuração FIRMS do sistema"""
import os, sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from app.core.config import settings

print("=== Diagnóstico FIRMS ===")
print(f"NASA_FIRMS_API_KEY configurada: {bool(settings.NASA_FIRMS_API_KEY)}")
print(f"Tamanho da chave: {len(settings.NASA_FIRMS_API_KEY)}")

if settings.NASA_FIRMS_API_KEY:
    print(f"Prefixo: {settings.NASA_FIRMS_API_KEY[:8]}...")
else:
    print("⚠️  Chave vazia — usando fallback de CSVs públicos")

print(f"NASA_FIRMS_URL: {settings.NASA_FIRMS_URL}")
print(f"Ceará BBOX: {settings.CEARA_LON_MIN},{settings.CEARA_LAT_MIN},{settings.CEARA_LON_MAX},{settings.CEARA_LAT_MAX}")

# Check firms_real.py imports
from app.services.firms_real import FIRMS_MAP_KEY, FIRMS_API_AREA, FIRMS_SOURCES
print(f"\n=== firms_real.py ===")
print(f"FIRMS_MAP_KEY (de settings): {bool(FIRMS_MAP_KEY)}")
print(f"API_AREA template: {FIRMS_API_AREA}")
print(f"Fontes CSV públicas: {list(FIRMS_SOURCES.keys())}")

# Check firms_service.py
from app.services.firms_service import CEARA_BBOX
print(f"\n=== firms_service.py ===")
print(f"CEARA_BBOX: {CEARA_BBOX}")
