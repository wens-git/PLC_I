"""Archive exactly the verified delivery inventory; exclude working files."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from verify_delivery import validate


def archive(root, destination):
    root = root.resolve()
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors = validate(root, manifest, require_builds=True)
    if errors:
        raise ValueError('\n'.join(errors))
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Archive already exists: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'x', ZIP_DEFLATED, compresslevel=6) as output:
        output.write(root / 'MANIFEST.json', 'MANIFEST.json')
        for name in sorted(manifest['files']):
            output.write(root / name, name)
    with ZipFile(destination) as check:
        if check.testzip() is not None:
            raise ValueError('Archive CRC verification failed')
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    destination.with_suffix(destination.suffix + '.sha256').write_text(
        f'{digest}  {destination.name}\n', encoding='utf-8')
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(archive(Path(__file__).resolve().parents[1], args.output))
