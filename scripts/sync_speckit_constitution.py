#!/usr/bin/env python3
"""Copia la constitución aprobada al lugar donde Spec Kit la consulta."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
source=root/'docs/01-constitution.md'
target=root/'.specify/memory/constitution.md'
if not (root/'.specify').is_dir():
    print('Spec Kit no está inicializado: no se crea constitución derivada.')
    sys.exit(0)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(source.read_text(encoding='utf-8'),encoding='utf-8')
print('Constitución derivada sincronizada con',source)
