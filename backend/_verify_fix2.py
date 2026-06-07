"""Verify all agent imports work with langchain 1.3.2."""
import subprocess

code = """
import sys
sys.path.insert(0, "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend")

from app.agents.react_agent import criar_agente_react
print("=== LangGraph Pipeline ===")
print("Agente ReAct - OK")

from app.agents.explicador_agent import _criar_agente_explicador
print("Explicador - OK")

from app.agents.auditor_agent import criar_agente_auditor
print("Auditor - OK")

print()
print("=== Análise IA concluída ===")
"""

r = subprocess.run(
    [".venv/bin/python3", "-c", code],
    capture_output=True, text=True,
    cwd="/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend",
    env={
        "VIRTUAL_ENV": "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/.venv",
        "PATH": "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/.venv/bin:/usr/bin:/bin",
        "PYTHONPATH": "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend",
    }
)
print(r.stdout)
print(r.stderr)
