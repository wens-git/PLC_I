"""Native shell: local resources, one WebChannel, explicit lifecycle."""
from pathlib import Path
import logging

from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView

from .bridge import HmiBridge


class LocalResources(QWebEngineUrlRequestInterceptor):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root.resolve()

    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.scheme() in ('qrc', 'data', 'blob')
        if url.isLocalFile():
            allowed = Path(url.toLocalFile()).resolve().is_relative_to(self.root)
        if not allowed:
            info.block(True)


class HmiPage(QWebEnginePage):
    consoleMessage = Signal(str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root.resolve()

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == self.root / 'index.html'

    def javaScriptConsoleMessage(self, level, message, line, source):
        logging.info('Web %s:%s %s', source, line, message)
        self.consoleMessage.emit(message)


class HmiWindow(QMainWindow):
    shutdownFinished = Signal(str)

    def __init__(self, service, web_root):
        super().__init__()
        self.setWindowTitle('FM_GPTPRO · PySide6 设备控制台')
        self.resize(1360, 900)
        self.setMinimumSize(900, 640)
        self.loading = True
        self.shutting_down = False
        self.can_close = False
        self.view = QWebEngineView(self)
        self.page = HmiPage(Path(web_root), self.view)
        self.view.setPage(self.page)
        self.interceptor = LocalResources(Path(web_root), self.page)
        self.page.profile().setUrlRequestInterceptor(self.interceptor)
        self.page.profile().downloadRequested.connect(lambda download: download.cancel())
        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        self.bridge = HmiBridge(service, self)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject('hmi', self.bridge)
        self.page.setWebChannel(self.channel)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setCentralWidget(self.view)
        self.view.loadStarted.connect(self._loading)
        self.view.loadFinished.connect(self._loaded)
        self.view.renderProcessTerminated.connect(self._renderer_failed)
        self.bridge.closed.connect(self._closed)
        QApplication.instance().applicationStateChanged.connect(self._application_state)
        self.view.load(QUrl.fromLocalFile(str(Path(web_root).resolve() / 'index.html')))

    def _loading(self):
        self.loading = True
        self.bridge.suspend(new_page=True)

    def _loaded(self, ok):
        self.loading = not ok
        if ok:
            self.statusBar().clearMessage()
            self._update_interaction()
        else:
            self.statusBar().showMessage('界面加载失败，请检查程序资源后重新启动')

    def _renderer_failed(self, status, code):
        self.bridge.suspend(new_page=True)
        self.statusBar().showMessage('界面进程异常，点动已撤销；请退出后重新启动')
        self.loading = True

    def _application_state(self, state):
        self._update_interaction()

    def _update_interaction(self):
        if self.loading or self.isMinimized() or not self.isActiveWindow():
            self.bridge.suspend()
        else:
            self.bridge.resume()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, 'bridge') and event.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            self._update_interaction()

    def closeEvent(self, event):
        if self.can_close:
            event.accept()
            return
        event.ignore()
        if not self.shutting_down:
            self.shutting_down = True
            self.view.setEnabled(False)
            self.statusBar().showMessage('正在撤销点动并关闭通信…')
            self.bridge.close()

    def _closed(self, error):
        if error:
            self.statusBar().showMessage('通信退出失败：' + error)
            self.shutdownFinished.emit(error)
            return
        self.can_close = True
        self.shutdownFinished.emit('')
        self.close()
