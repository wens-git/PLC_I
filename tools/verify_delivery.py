"""Verify all immutable delivery files against MANIFEST.json."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
errors = []
for name, expected in manifest['files'].items():
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append(name)
if errors:
    raise SystemExit('Missing or modified delivery files:\n' + '\n'.join(errors))
print('Verified', len(manifest['files']), 'delivery files; exactly one current PLC project:',
      len(list((root / 'plc').rglob('*.project'))) == 1)
