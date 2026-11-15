"""Small delivery regression tests, with disposable fake packages and no build tools."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_manifest import digest, make_manifest, source_hashes
from verify_delivery import validate


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        # Keep fixtures under the authorized workspace, rather than OS user temp.
        fixture_parent = Path(__file__).resolve().parents[2] / 'artifacts/delivery-tests'
        fixture_parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixture_parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, data in {
            'plc/project/current.project': b'current project',
            'plc/project/historical.project': b'baseline',
            'plc/src/main.st': b'PROGRAM PLC_PRG END_PROGRAM',
            'desktop/main.py': b'print("hello")',
            'App/FM_GPTPRO.exe': b'MZfake-test-executable',
            'App/_internal/runtime.dll': b'runtime',
            'App/FM_GPTPRO-data/desktop.log': b'user log',
            'plc/project/current.opt': b'IDE preference',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def manifest(self, **kwargs):
        return make_manifest(self.root, 'plc/project/current.project', **kwargs)

    def evidence(self, kind):
        record = {'success': True, 'completed_at': datetime.now(timezone.utc).isoformat(),
                  'sources': source_hashes(self.root, kind)}
        if kind == 'plc':
            record.update(production_project='plc/project/current.project',
                          project_sha256=digest(self.root / 'plc/project/current.project'))
        else:
            record['executable_sha256'] = digest(self.root / 'App/FM_GPTPRO.exe')
        name = f'artifacts/{kind}-evidence.json'
        path = self.root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(record), encoding='utf-8')
        return name

    def test_multiple_projects_allowed_mutable_files_excluded_and_no_inherited_passes(self):
        manifest = self.manifest()
        self.assertEqual(validate(self.root, manifest), [])
        self.assertIn('plc/project/historical.project', manifest['files'])
        self.assertNotIn('plc/project/current.opt', manifest['files'])
        self.assertNotIn('App/FM_GPTPRO-data/desktop.log', manifest['files'])
        self.assertTrue(all(v['status'] == 'not_run' for v in manifest['verification'].values()))
        self.assertTrue(validate(self.root, manifest, require_builds=True))

    def test_fresh_builds_and_changed_source_rejected_even_if_inventory_updated(self):
        manifest = self.manifest(plc_evidence=self.evidence('plc'),
                                 desktop_evidence=self.evidence('desktop'))
        self.assertEqual(validate(self.root, manifest, require_builds=True), [])
        path = self.root / 'plc/src/main.st'
        path.write_bytes(b'new source')
        manifest['files']['plc/src/main.st'] = digest(path)
        manifest['plc_sources'] = source_hashes(self.root, 'plc')
        self.assertTrue(any('Evidence sources' in e for e in validate(self.root, manifest)))

    def test_wrong_primary_project_or_missing_executable_fail(self):
        manifest = self.manifest()
        changed = copy.deepcopy(manifest)
        changed['production_project']['path'] = 'plc/project/missing.project'
        self.assertTrue(validate(self.root, changed))
        (self.root / 'App/FM_GPTPRO.exe').unlink()
        self.assertTrue(validate(self.root, manifest))
        with self.assertRaises(ValueError):
            self.manifest()

    def test_unlisted_source_and_path_escape_fail(self):
        manifest = self.manifest()
        (self.root / 'desktop/new.py').write_text('new', encoding='utf-8')
        self.assertTrue(validate(self.root, manifest))
        manifest['files']['../outside'] = 'bad'
        self.assertTrue(validate(self.root, manifest))

    def test_packaged_protocol_is_an_output_not_a_desktop_source(self):
        before = source_hashes(self.root, 'desktop')
        path = self.root / 'App/_internal/docs/protocol-v1.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}', encoding='utf-8')
        self.assertEqual(source_hashes(self.root, 'desktop'), before)

    def test_old_evidence_without_project_binding_rejected(self):
        name = self.evidence('plc')
        path = self.root / name
        record = json.loads(path.read_text(encoding='utf-8'))
        del record['project_sha256']
        path.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'subject hash'):
            self.manifest(plc_evidence=name)


if __name__ == '__main__':
    unittest.main()
