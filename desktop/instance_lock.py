"""Per-user Windows byte lock, released by the OS even on process termination."""
import msvcrt
from pathlib import Path


class InstanceLock:
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None
        self.error = None

    def acquire(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            stream = self.path.open('a+b')
            if stream.seek(0, 2) == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                stream.close()
                raise
            self.stream = stream
            return True
        except OSError as exc:
            self.error = str(exc)
            return False

    def release(self):
        if self.stream is not None:
            try:
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.stream.close()
                self.stream = None
