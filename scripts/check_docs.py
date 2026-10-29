#!/usr/bin/env python3
"""Validación estática ligera de estructura SDD; no sustituye pruebas del producto."""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=[
 'README.md', 'AGENTS.md', 'docs/00-vision.md', 'docs/01-constitution.md',
 'docs/02-architecture.md', 'docs/03-tenancy-security.md',
 'docs/04-data-model.md', 'docs/05-ingestion.md', 'docs/06-retrieval.md',
 'docs/07-api-contracts.md', 'docs/08-operations.md',
 'docs/09-nfr-quality.md', 'docs/10-roadmap.md', 'docs/11-sdd-codex.md',
 'docs/12-threat-model.md', 'docs/13-decisions-risks.md',
 'ops/FIRST_CODEX_TASK.md',
]
issues=[]
for name in REQUIRED:
    p=ROOT/name
    if not p.is_file() or not p.read_text(encoding='utf-8').strip():
        issues.append(f'Missing or empty: {name}')

for i in range(12):
    code=f'F{i:02d}'
    dirs=list((ROOT/'specs').glob(code+'-*'))
    if len(dirs)!=1:
        issues.append(f'{code}: expected exactly one phase directory, found {len(dirs)}')
        continue
    s=dirs[0]/'spec.md'
    if not s.exists():
        issues.append(f'{code}: missing spec.md')
        continue
    content=s.read_text(encoding='utf-8')
    if not re.search(r'AC-'+code+r'-\d+', content):
        issues.append(f'{code}: no traceable AC IDs')
    if not re.search(r'R\d\d?', content):
        issues.append(f'{code}: no requirement IDs')

constitution=(ROOT/'docs/01-constitution.md').read_text(encoding='utf-8')
for num in range(1,15):
    if not re.search(r'P'+str(num).zfill(2)+r'\b', constitution):
        issues.append(f'Constitution missing P{num:02d}')

# Si Spec Kit está instalado, su constitución es una copia derivada y debe coincidir.
speckit_constitution=ROOT/'.specify/memory/constitution.md'
if speckit_constitution.exists() and speckit_constitution.read_text(encoding='utf-8') != constitution:
    issues.append('Spec Kit constitution differs from canonical docs/01-constitution.md; run scripts/sync_speckit_constitution.py')

if issues:
    print('SDD DOCUMENTATION ERRORS:')
    for issue in issues:
        print(' - '+issue)
    sys.exit(1)
print('OK: required documents, 12 phase specs and 14 constitutional principles found.')
