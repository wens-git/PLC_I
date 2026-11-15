"""Single-instance exclusion must survive packaging and release on exit."""
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows desktop byte lock')


def test_lock_excludes_other_process_and_releases(tmp_path):
    from desktop.instance_lock import InstanceLock
    path = tmp_path / 'desktop.lock'
    lock = InstanceLock(path)
    assert lock.acquire()
    code = "from desktop.instance_lock import InstanceLock; import sys; x=InstanceLock(sys.argv[1]); ok=x.acquire(); x.release(); raise SystemExit(0 if ok else 3)"
    assert subprocess.run([sys.executable, '-c', code, str(path)]).returncode == 3
    lock.release()
    assert subprocess.run([sys.executable, '-c', code, str(path)]).returncode == 0


def test_occupied_first_candidate_never_falls_back(tmp_path):
    from desktop.instance_lock import InstanceLock
    first, second = tmp_path / 'install', tmp_path / 'data'
    lock, errors = InstanceLock.acquire_candidates([first, second])
    assert lock is not None and not errors
    code = "from desktop.instance_lock import InstanceLock; import sys; x, errors=InstanceLock.acquire_candidates(sys.argv[1:]); x and x.release(); raise SystemExit(0 if x else 3)"
    try:
        assert subprocess.run([sys.executable, '-c', code, str(first), str(second)]).returncode == 3
        assert not (second / 'desktop.lock').exists()
    finally:
        lock.release()
    assert subprocess.run([sys.executable, '-c', code, str(first), str(second)]).returncode == 0


def test_unavailable_directory_allows_fallback(tmp_path):
    from desktop.instance_lock import InstanceLock
    unavailable = tmp_path / 'file-not-directory'
    unavailable.write_text('occupied by a file')
    fallback = tmp_path / 'data'
    lock, errors = InstanceLock.acquire_candidates([unavailable, fallback])
    assert lock is not None and len(errors) == 1
    try:
        assert lock.path.parent == fallback
    finally:
        lock.release()
