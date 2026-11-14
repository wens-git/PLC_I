"""Start the offline PySide6/QWebChannel application. No HTTP listener."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

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
    app = QApplication(sys.argv[:1])
    app.setApplicationName('FM_GPTPRO')
    app.setOrganizationName('FM_GPTPRO')
    data_dir = args.data_dir or Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'FM_GPTPRO'
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir / 'desktop.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    # A fixed per-user directory prevents duplicate instances even with --data-dir.
    # Keep the lock with application data: some Windows environments permit Python
    # in TEMP but deny a packaged executable creating a lock there.
    lock_dir = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'FM_GPTPRO'
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = InstanceLock(lock_dir / 'desktop.lock')
    if not lock.acquire():
        logging.error('Desktop lock failed: error=%s directory=%s', lock.error, lock_dir)
        if args.smoke_report:
            logging.error('Smoke cannot start without the per-user application lock')
            return 1
        QMessageBox.information(None, 'FM_GPTPRO', '设备控制台已经运行或无法取得应用锁，请检查桌面日志。')
        return 1
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
