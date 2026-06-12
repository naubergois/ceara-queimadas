#!/usr/bin/env python3
"""Verifica se a chave FIRMS está configurada corretamente no .env"""
import os

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith('NASA_FIRMS_API_KEY='):
            val = line.split('=', 1)[1]
            print(f"Length: {len(val)}")
            print(f"Is empty: {len(val) == 0}")
            print(f"Has placeholder: {'sua-chave' in val or 'change' in val}")
            print(f"Prefix: {val[:10]}...")
            break
