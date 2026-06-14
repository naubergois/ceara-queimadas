#!/usr/bin/env python3
"""Validador de sintaxe dos módulos do dashboard."""
import ast
import os
import sys

MODULES = [
    "backend/app/dashboard/offline_data.py",
    "backend/app/dashboard/dashboard.py",
    "backend/app/dashboard/test_dashboard_structure.py",
]

root = os.path.expanduser("~/QueimandasGemeosDigitais/ceara-queimadas")
all_ok = True
for mod in MODULES:
    path = os.path.join(root, mod)
    if not os.path.exists(path):
        print(f"⚠️  Não encontrado: {path}")
        continue
    with open(path) as f:
        source = f.read()
    try:
        tree = ast.parse(source)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        print(f"✅ {mod} — {len(funcs)} funções, {source.count(chr(10))} linhas")
    except SyntaxError as e:
        print(f"❌ {mod} — ERRO: {e}")
        all_ok = False

sys.exit(0 if all_ok else 1)
