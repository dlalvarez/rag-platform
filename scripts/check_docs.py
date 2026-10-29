#!/usr/bin/env python3
"""Validación estática de integridad documental SDD y rutas locales."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md', 'AGENTS.md', 'CONSTITUTION.md', '.gitignore',
    '.github/workflows/docs.yml', 'docs/00-vision.md',
    'docs/01-constitution.md', 'docs/02-architecture.md',
    'docs/03-tenancy-security.md', 'docs/04-data-model.md',
    'docs/05-ingestion.md', 'docs/06-retrieval.md',
    'docs/07-api-contracts.md', 'docs/08-operations.md',
    'docs/09-nfr-quality.md', 'docs/10-roadmap.md',
    'docs/11-sdd-codex.md', 'docs/12-threat-model.md',
    'docs/13-decisions-risks.md', 'docs/14-release-and-governance.md',
    'docs/roadmap.md', 'docs/architecture/overview.md',
    'ops/DECISION_STATUS.md', 'ops/CODEX_PROMPTS.md',
    'ops/FIRST_CODEX_TASK.md', 'ops/BOOTSTRAP.md',
    'tests/acceptance/tenant-isolation.md',
    'specs/F00-fundacion-repositorio/plan.md',
    'specs/F00-fundacion-repositorio/tasks.md',
    'specs/F00-fundacion-repositorio/checklist.md',
    'specs/F00-fundacion-repositorio/evidence.md',
    'specs/F01-aislamiento-provisionamiento/plan.md',
    'specs/F01-aislamiento-provisionamiento/tasks.md',
]
errors = []
for name in REQUIRED:
    file = ROOT / name
    if not file.is_file() or not file.read_text(encoding='utf-8').strip():
        errors.append(f'Missing or empty: {name}')

for i in range(12):
    phase = f'F{i:02d}'
    dirs = [d for d in (ROOT / 'specs').glob(f'{phase}-*') if d.is_dir()]
    if len(dirs) != 1:
        errors.append(f'{phase}: expected one active phase folder, found {len(dirs)}')
        continue
    spec = dirs[0] / 'spec.md'
    if not spec.is_file():
        errors.append(f'{phase}: missing spec.md')
        continue
    contents = spec.read_text(encoding='utf-8')
    if not re.search(rf'AC-{phase}-\d\d\b', contents):
        errors.append(f'{phase}: acceptance criteria IDs absent')
    if not re.search(rf'\b{phase}-R\d\d\b', contents):
        errors.append(f'{phase}: requirement IDs absent')

constitution = ROOT / 'docs/01-constitution.md'
if constitution.is_file():
    contents = constitution.read_text(encoding='utf-8')
    for i in range(1, 15):
        if not re.search(rf'\bP{i:02d}\b', contents):
            errors.append(f'Constitution missing P{i:02d}')

for path, canonical in [
    ('CONSTITUTION.md', 'docs/01-constitution.md'),
    ('docs/roadmap.md', 'docs/10-roadmap.md'),
]:
    f = ROOT / path
    if f.is_file() and canonical not in f.read_text(encoding='utf-8'):
        errors.append(f'{path} must point to {canonical}')

adr_dir = ROOT / 'docs/adr'
if adr_dir.is_dir():
    for i in range(1, 6):
        if len(list(adr_dir.glob(f'{i:04d}-*.md'))) != 1:
            errors.append(f'ADR {i:04d}: expected one uniquely numbered file')

# Las copias en history son registros históricos, no contratos actuales.
md_link = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
for file in ROOT.rglob('*.md'):
    if 'history' in file.relative_to(ROOT).parts:
        continue
    text = file.read_text(encoding='utf-8')
    for match in md_link.finditer(text):
        target = match.group(1).split('#', 1)[0]
        if not target or target.startswith(('https://', 'http://', 'mailto:', '/')):
            continue
        if not (file.parent / target).exists():
            errors.append(f'Broken local link in {file.relative_to(ROOT)}: {target}')

speckit = ROOT / '.specify/memory/constitution.md'
if speckit.is_file() and constitution.is_file():
    if speckit.read_text(encoding='utf-8') != constitution.read_text(encoding='utf-8'):
        errors.append('Spec Kit constitution differs; run scripts/sync_speckit_constitution.py')

if errors:
    print('SDD DOCUMENTATION ERRORS:')
    for issue in errors:
        print(' -', issue)
    sys.exit(1)
print('OK: SDD baseline, 12 phases, P01-P14, canonical references, ADRs and links.')
