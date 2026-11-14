"""Current PLC source identity; does not invoke an IEC compiler."""
import hashlib
import json
from pathlib import Path


def test_current_plc_sources_match_latest_compiler_record():
    root = Path(__file__).resolve().parents[2]
    evidence = root / 'plc/evidence/cylinder-upgrade-build-status.json'
    status = json.loads(evidence.read_text(encoding='utf-8'))
    assert status['success'] is True
    assert status['offline_only'] is True
    current_sources = {str(path.relative_to(root)).replace('\\', '/')
                       for path in (root / 'plc/src').rglob('*.st')}
    assert {name.replace('\\', '/') for name in status['sources']} == current_sources
    for name, expected in status['sources'].items():
        path = root / name.replace('\\', '/')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
