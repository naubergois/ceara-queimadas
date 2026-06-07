#!/usr/bin/env python3
"""Check create_agent from langchain.agents."""
import subprocess

code = r'''
from langchain.agents import create_agent
import inspect
sig = inspect.signature(create_agent)
print(sig)
'''

r = subprocess.run(
    ["python3", "-c", code],
    capture_output=True, text=True,
    cwd="/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend",
    env={"VIRTUAL_ENV": "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/.venv", "PATH": "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/.venv/bin:/usr/bin:/bin"}
)
print(r.stdout)
print(r.stderr)
