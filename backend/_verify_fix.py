#!/usr/bin/env python3
"""Fixes applied to the queimadas agent code for langchain 1.3.2 compatibility."""

from hermes_tools import terminal

# Run the same checks as the pre-run script
r = terminal("cd /Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend && .venv/bin/python3 -c \"from app.agents.react_agent import criar_agente_react; print('LangGraph Pipeline - OK')\" 2>&1")
print("=== LangGraph Pipeline ===")
print(r["output"])

r2 = terminal("cd /Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend && .venv/bin/python3 -c \"from app.agents.react_agent import criar_agente_react; print('Agente ReAct - OK')\" 2>&1")
print("=== Agente ReAct ===")
print(r2["output"])

r3 = terminal("cd /Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend && .venv/bin/python3 -c \"from app.agents.explicador_agent import _criar_agente_explicador; print('Explicador - OK')\" 2>&1")
print("=== Explicador ===")
print(r3["output"])

r4 = terminal("cd /Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend && .venv/bin/python3 -c \"from app.agents.auditor_agent import criar_agente_auditor; print('Auditor - OK')\" 2>&1")
print("=== Auditor ===")
print(r4["output"])
