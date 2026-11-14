"""Refresh delivery hashes after the 1.3 build, preserving historical evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'MANIFEST.json'
old = json.loads(path.read_text(encoding='utf-8'))
backup = ROOT / 'Validation/MANIFEST-before-cylinder-v13.json'
if not backup.exists():
    backup.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
old['date'] = '2026-11-13'
old['protocol_revision'] = '1.3'
old['verification'] = json.loads((ROOT / 'Validation/cylinder-upgrade-results.json').read_text(encoding='utf-8'))
project = ROOT / 'plc/project/FM_XJV1_Cylinder_v13.project'
old['plc_project'] = {'path': str(project.relative_to(ROOT)).replace('\\', '/'),
    'source': 'Offline XS Studio rebuild of current 47 source files',
    'sha256': hashlib.sha256(project.read_bytes()).hexdigest()}
files = {}
for directory in ('App', 'backend', 'desktop', 'docs', 'plc', 'tools', 'web/src', 'web/dist', 'web/tests'):
    for item in (ROOT / directory).rglob('*'):
        if item.is_file() and '__pycache__' not in item.parts and item.suffix not in ('.pyc', '.bak'):
            files[item.relative_to(ROOT).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
for item in ROOT.iterdir():
    if item.is_file() and item.name != 'MANIFEST.json':
        files[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
old['files'] = dict(sorted(files.items()))
path.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Updated delivery manifest:', len(files), 'files; historical manifest preserved in Validation')
