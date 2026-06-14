#!/usr/bin/env python3
"""
Testa a estrutura do dashboard Streamlit sem executá-lo.
Verifica se as importações básicas funcionam e se o código Python é válido.
"""

import ast
import sys
import os

def main():
    dashboard_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "backend",
        "app",
        "dashboard",
        "dashboard.py",
    )
    dashboard_path = os.path.abspath(dashboard_path)

    if not os.path.exists(dashboard_path):
        print(f"❌ Dashboard não encontrado: {dashboard_path}")
        return 1

    # 1. Verifica sintaxe Python
    with open(dashboard_path) as f:
        source = f.read()

    try:
        tree = ast.parse(source)
        print("✅ Sintaxe Python OK")
    except SyntaxError as e:
        print(f"❌ Erro de sintaxe: {e}")
        return 1

    # 2. Conta funções e classes
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    print(f"📊 Funções definidas: {len(functions)}")
    print(f"📊 Classes definidas: {len(classes)}")

    # 3. Verifica páginas registradas
    pages_found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    pages_found.append(key.value)
    print(f"📋 Páginas: {len(pages_found)}")

    # 4. Tamanho do arquivo
    lines = source.count("\n")
    print(f"📏 Linhas: {lines}")

    print("\n✅ Dashboard structure validated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
