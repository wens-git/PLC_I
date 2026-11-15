"""Start the offline PySide6/QWebChannel application. No HTTP listener."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile

from desktop.instance_lock import InstanceLock
from PySide6.QtWidgets import QApplication, QMessageBox

from backend.service import HmiService
from backend.xj_protocol import ROOT
from desktop.window import HmiWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--smoke-report', type=Path, help='Run deterministic mock-only desktop validation and exit')
    parser.add_argument('--fullscreen', action='store_true')
    args = parser.parse_args()
    # Local-only content: render in-process so managed/restricted desktops that block
    # the WebEngine renderer child process still start. Override via environment.
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--no-sandbox --single-process --disable-gpu')
    os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    app = QApplication(sys.argv[:1])
    app.setApplicationName('FM_GPTPRO')
    app.setOrganizationName('FM_GPTPRO')
    def writable(path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / '.write-test'
            probe.write_text('ok', encoding='utf-8')
            probe.unlink()
            return True
        except OSError:
            return False

    if args.data_dir:
        data_dir = args.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        # Restricted profiles can deny %LOCALAPPDATA%; fall back to the install
        # directory, then to a temp directory, instead of failing to start.
        preferred = [Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'FM_GPTPRO']
        if getattr(sys, 'frozen', False):
            preferred.append(Path(sys.executable).resolve().parent / 'FM_GPTPRO-data')
        preferred.append(Path(tempfile.gettempdir()) / 'FM_GPTPRO')
        data_dir = next((path for path in preferred if writable(path)), preferred[-1])
        data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir / 'desktop.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    # One desktop instance per installation. Try writable candidates in order so a
    # packaged EXE with a restricted profile still starts; every real duplicate
    # fails on the same first writable candidate.
    candidates = [Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
                  else ROOT, data_dir, Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'FM_GPTPRO']
    lock = None
    lock_errors = []
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            lock_errors.append(f'{candidate}: {error}')
            continue
        attempt = InstanceLock(candidate / 'desktop.lock')
        if attempt.acquire():
            lock, lock_dir = attempt, candidate
            break
        lock_errors.append(f'{candidate}: {attempt.error}')
    if lock is None:
        logging.error('Desktop lock failed: %s', '; '.join(lock_errors))
        if args.smoke_report:
            logging.error('Smoke cannot start without the application lock')
            return 1
        QMessageBox.information(None, 'FM_GPTPRO', '设备控制台已经运行或无法取得应用锁，请检查桌面日志。')
        return 1
    logging.info('Desktop lock acquired in %s', lock_dir)
    web_root = ROOT / 'web/dist'
    if not (web_root / 'index.html').is_file():
        QMessageBox.critical(None, '资源缺失', '界面资源缺失，请先运行 web 目录下的 npm run build。')
        return 1
    service = HmiService(data_dir / 'simulation.json')
    window = HmiWindow(service, web_root)
    window.showFullScreen() if args.fullscreen else window.show()
    if args.smoke_report:
        from desktop.smoke import DesktopSmoke
        window.smoke = DesktopSmoke(window, args.smoke_report)
    result = app.exec()
    service.close()
    lock.release()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
