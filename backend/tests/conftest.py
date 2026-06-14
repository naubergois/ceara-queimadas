"""Configuração compartilhada dos testes do backend."""
import sys
from pathlib import Path

# Adiciona backend ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))
