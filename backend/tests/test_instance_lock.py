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
