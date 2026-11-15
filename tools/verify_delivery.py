"""Verify delivery integrity and current-source evidence; exit nonzero on failure."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from generate_manifest import CHECKS, digest, included, inventory, local_path, source_hashes


def validate(root, manifest, require_builds=False):
    errors = []
    if manifest.get('format') != 2:
        return ['Unsupported/legacy manifest: regenerate format 2; old acceptance is not current evidence.']
    files = manifest.get('files', {})

    def check_ref(ref):
        path = local_path(root, ref['path'])
        if not path.is_file() or digest(path) != ref['sha256']:
            raise ValueError('Missing or modified: ' + ref['path'])
        if files.get(ref['path']) != ref['sha256']:
            raise ValueError('Reference missing from inventory: ' + ref['path'])
        return path

    def current_evidence(record, expected_sources, subject=None):
        path = check_ref(record['evidence'])
        evidence = json.loads(path.read_text(encoding='utf-8-sig'))
        if evidence.get('success') is not True:
            raise ValueError('Evidence does not report success: ' + str(path))
        completed = datetime.fromisoformat(evidence['completed_at'].replace('Z', '+00:00'))
        generated = datetime.fromisoformat(manifest['generated_at'])
        if completed.tzinfo is None or completed > generated:
            raise ValueError('Evidence completion must be timezone-aware and precede manifest')
        actual = {name.replace('\\', '/'): value for name, value in evidence['sources'].items()}
        if actual != expected_sources or not actual:
            raise ValueError('Evidence sources do not match the complete current source set: ' + str(path))
        if subject:
            key, ref = subject
            if evidence.get(key) != ref['sha256']:
                raise ValueError('Evidence subject hash does not match: ' + key)
        return evidence

    try:
        if not files:
            errors.append('Empty file inventory')
        for name, expected in files.items():
            path = local_path(root, name)
            if not included(name) and not any(
                record.get('evidence', {}).get('path') == name
                for record in [manifest.get('plc_build', {}), manifest.get('desktop_build', {}),
                               *manifest.get('verification', {}).values()]):
                errors.append('Mutable/excluded file in inventory: ' + name)
            if not path.is_file() or digest(path) != expected:
                errors.append('Missing or modified: ' + name)
        extra = set(inventory(root)) - set(files)
        if extra:
            errors.append('Unlisted delivery files: ' + ', '.join(sorted(extra)))
        project = manifest['production_project']
        project_path = check_ref(project)
        if not project['path'].startswith('plc/project/') or project_path.suffix != '.project':
            errors.append('Invalid production_project; expected plc/project/*.project')
        exe = manifest['desktop_executable']
        exe_path = check_ref(exe)
        with exe_path.open('rb') as stream:
            executable_header = stream.read(2)
        if exe['path'] != 'App/FM_GPTPRO.exe' or executable_header != b'MZ':
            errors.append('Invalid App/FM_GPTPRO.exe Windows executable')
        if not (root / 'App/_internal').is_dir() or not any((root / 'App/_internal').iterdir()):
            errors.append('Missing/empty App/_internal runtime directory')
        for kind in ('plc', 'desktop'):
            expected_sources = source_hashes(root, kind)
            if manifest[kind + '_sources'] != expected_sources or not expected_sources:
                errors.append(kind + ' current source hashes differ from manifest')
            record = manifest[kind + '_build']
            if record['status'] == 'passed':
                subject = ('project_sha256', project) if kind == 'plc' else ('executable_sha256', exe)
                evidence = current_evidence(record, expected_sources, subject)
                if kind == 'plc' and evidence.get('production_project') != project['path']:
                    errors.append('PLC evidence production_project differs from manifest')
            elif record['status'] != 'not_run' or require_builds:
                errors.append(kind + ' build has no successful current evidence')
        checks = manifest['verification']
        if set(checks) != set(CHECKS):
            errors.append('Verification check set differs from supported checks')
        for name, record in checks.items():
            status = record.get('status')
            if status in {'passed', 'failed'}:
                # A report must bind itself to current sources, not merely an old pass count.
                current_evidence(record, manifest['desktop_sources'])
                if status == 'failed':
                    errors.append('Verification failed: ' + name)
                if name == 'packaged_smoke':
                    evidence = json.loads(check_ref(record['evidence']).read_text(encoding='utf-8-sig'))
                    if evidence.get('executable_sha256') != exe['sha256']:
                        errors.append('Packaged smoke executable hash differs')
            elif status != 'not_run':
                errors.append('Invalid verification status: ' + name)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--require-builds', action='store_true', help='Require current PLC and desktop build evidence')
    args = parser.parse_args()
    try:
        manifest = json.loads((args.root / 'MANIFEST.json').read_text(encoding='utf-8-sig'))
        errors = validate(args.root.resolve(), manifest, args.require_builds)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        parser.exit(1, 'Delivery verification FAILED:\n' + '\n'.join(errors) + '\n')
    print('Verified', len(manifest['files']), 'files; production_project:', manifest['production_project']['path'])
    print('Builds:', {kind: manifest[kind + '_build']['status'] for kind in ('plc', 'desktop')})
    print('Checks:', {name: record['status'] for name, record in manifest['verification'].items()})


if __name__ == '__main__':
    main()
