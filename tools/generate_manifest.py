"""Generate a new delivery inventory; never import acceptance claims from an old manifest."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

EXCLUDED_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache',
                 '.npm-cache', 'artifacts', 'build', '.idea', '.vs', '.vscode'}
EXCLUDED_SUFFIXES = {'.log', '.lock', '.opt', '.pyc', '.pyo', '.autosave', '.compileinfo',
                     '.bootinfo', '.bootinfo_guids'}
CHECKS = ('python_tests', 'frontend_tests', 'protocol_check', 'source_smoke',
          'packaged_smoke', 'real_plc_acceptance')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def local_path(root, name):
    """Reject traversal, absolute paths and paths through external symlinks."""
    name = str(name).replace('\\', '/')
    path = Path(name)
    if path.is_absolute() or ':' in name or '..' in path.parts:
        raise ValueError('Expected delivery-relative path: ' + name)
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('Path escapes delivery: ' + name)
    return resolved


def included(name):
    path = Path(name)
    return (not any(p in EXCLUDED_DIRS or p.endswith('-data') for p in path.parts)
            and path.suffix.lower() not in EXCLUDED_SUFFIXES
            and '.log.' not in path.name.lower()
            and '.project.~u' not in path.name
            and path.name != 'MANIFEST.json')


def delivery_paths(root):
    # Prune caches/artifacts before traversal (node_modules may contain thousands of files).
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if included(
            (Path(directory) / d).relative_to(root).as_posix()))
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if included(relative):
                local_path(root, relative)
                yield path


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in delivery_paths(root)}


def source_hashes(root, kind):
    if kind == 'plc':
        paths = (root / 'plc/src').rglob('*.st')
    else:
        paths = (p for p in delivery_paths(root) if p.is_file() and (
            p.relative_to(root).parts[0] in {'backend', 'desktop', 'web'}
            or p.relative_to(root).as_posix() in {'DesktopHMI.spec', 'desktop_launcher.py',
                          'requirements.txt', 'requirements-dev.txt', 'requirements-desktop.txt',
                          'docs/protocol-v1.json'}))
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths)
            if p.is_file() and included(p.relative_to(root).as_posix())
            and 'dist' not in p.relative_to(root).parts}


def reference(root, name):
    path = local_path(root, name)
    if not path.is_file():
        raise ValueError('Missing file: ' + str(name))
    return {'path': path.relative_to(root).as_posix(), 'sha256': digest(path)}


def make_manifest(root, project, plc_evidence=None, desktop_evidence=None, verification=None):
    root = root.resolve()
    project_ref = reference(root, project)
    if not project_ref['path'].startswith('plc/project/') or not project_ref['path'].endswith('.project'):
        raise ValueError('production_project must name a plc/project/*.project file')
    checks = {name: {'status': 'not_run'} for name in CHECKS}
    if verification:
        supplied = json.loads(local_path(root, verification).read_text(encoding='utf-8-sig'))
        unknown = set(supplied) - set(CHECKS)
        if unknown:
            raise ValueError('Unknown verification checks: ' + ', '.join(sorted(unknown)))
        for name, record in supplied.items():
            if record.get('status') not in {'passed', 'failed', 'not_run'}:
                raise ValueError('Invalid verification status: ' + name)
            checks[name] = record
    manifest = {
        'format': 2, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'product': 'FM_GPTPRO PySide6 + Web + QWebChannel',
        'production_project': project_ref,
        'plc_sources': source_hashes(root, 'plc'),
        'desktop_sources': source_hashes(root, 'desktop'),
        'desktop_executable': reference(root, 'App/FM_GPTPRO.exe'),
        'plc_build': {'status': 'not_run'}, 'desktop_build': {'status': 'not_run'},
        'verification': checks,
        'limitations': ['Only explicitly supplied current-run evidence records are reported.',
                        'File integrity is not PLC compilation, execution or physical acceptance.'],
    }
    for key, name in [('plc_build', plc_evidence), ('desktop_build', desktop_evidence)]:
        if name:
            manifest[key] = {'status': 'passed', 'evidence': reference(root, name)}
    manifest['files'] = inventory(root)
    # Explicitly referenced evidence may be in artifacts, which is otherwise excluded.
    for record in [manifest['plc_build'], manifest['desktop_build'], *checks.values()]:
        if record.get('evidence'):
            ref = record['evidence']
            ref = reference(root, ref if isinstance(ref, str) else ref['path'])
            record['evidence'] = ref
            manifest['files'][ref['path']] = ref['sha256']
    from verify_delivery import validate
    errors = validate(root, manifest)
    if errors:
        raise ValueError('\n'.join(errors))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--production-project', required=True)
    parser.add_argument('--plc-evidence')
    parser.add_argument('--desktop-evidence')
    parser.add_argument('--verification', help='JSON check records, default all not_run')
    args = parser.parse_args()
    try:
        manifest = make_manifest(args.root, args.production_project, args.plc_evidence,
                                 args.desktop_evidence, args.verification)
        (args.root / 'MANIFEST.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, str(exc) + '\n')
    print('Generated MANIFEST.json; unexecuted checks remain not_run.')


if __name__ == '__main__':
    main()
