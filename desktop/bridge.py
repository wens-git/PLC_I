"""Asynchronous, bounded QWebChannel adapter. Qt never performs PLC I/O."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Thread, Lock

from fastapi import HTTPException
from pydantic import ValidationError
from PySide6.QtCore import QObject, Signal, Slot, QTimer


class HmiBridge(QObject):
    response = Signal(str)
    snapshot = Signal(str)
    suspended = Signal()
    closed = Signal(str)
    _packet = Signal(int, str)
    _state = Signal(str)
    _shutdown_done = Signal(str)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.closing = False
        self.page_epoch = 0
        self.pending = set()
        self.pending_lock = Lock()
        self.commands = ThreadPoolExecutor(max_workers=4, thread_name_prefix='hmi-rpc')
        self.controls = ThreadPoolExecutor(max_workers=2, thread_name_prefix='hmi-control')
        self.states = ThreadPoolExecutor(max_workers=1, thread_name_prefix='hmi-state')
        self.state_future = None
        self._packet.connect(self._deliver)
        self._state.connect(self.snapshot)
        self._shutdown_done.connect(self.closed)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.publish)
        self.timer.start()

    @Slot(str)
    def request(self, raw):
        request_id = ''
        try:
            if len(raw) > 65536:
                raise ValueError('请求过大')
            packet = json.loads(raw)
            request_id = packet['id']
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
                raise ValueError('请求编号非法')
            if self.closing:
                raise HTTPException(409, '应用正在关闭')
            method, path = packet['method'], packet['path']
            if not isinstance(method, str) or not isinstance(path, str):
                raise ValueError('请求方法或路径非法')
            payload = packet.get('payload', {})
            epoch = self.service.interaction_epoch
            # Stop and renew must remain runnable while ordinary requests wait for ACK.
            priority = path in ('/api/jog/stop', '/api/jog/renew') or (
                path == '/api/command' and isinstance(payload, dict) and payload.get('code') in (9, 10, 26, 42))
            with self.pending_lock:
                if len(self.pending) >= (48 if priority else 40):
                    raise HTTPException(429, '请求队列已满，请等待当前操作完成')
            pool = self.controls if priority else self.commands
            page_epoch = self.page_epoch
            future = pool.submit(self._execute, method, path, payload, epoch, page_epoch)
            with self.pending_lock:
                self.pending.add(future)
            future.add_done_callback(lambda completed: self._reply(request_id, completed, page_epoch))
        except Exception as error:
            self.response.emit(self._encode_error(request_id, error))

    def _execute(self, method, path, payload, epoch, page_epoch):
        if self.closing or page_epoch != self.page_epoch:
            raise HTTPException(409, '页面已变化，请重新操作')
        return self.service.dispatch(method, path, payload, interaction_epoch=epoch)

    @staticmethod
    def _encode_error(request_id, error):
        if isinstance(error, HTTPException):
            status, detail = error.status_code, error.detail
        elif isinstance(error, ValidationError):
            status, detail = 422, str(error)
        elif isinstance(error, (ValueError, KeyError, TypeError)):
            status, detail = 422, str(error)
        elif isinstance(error, RuntimeError):
            status, detail = 409, str(error)
        else:
            logging.exception('Native request failed', exc_info=error)
            status, detail = 500, '桌面服务异常，请查看日志；已发送命令结果未知'
        return json.dumps({'id': request_id, 'status': status, 'body': {'detail': detail}}, ensure_ascii=False)

    def _reply(self, request_id, future, page_epoch):
        with self.pending_lock:
            self.pending.discard(future)
        if self.closing or page_epoch != self.page_epoch:
            return
        try:
            packet = json.dumps({'id': request_id, 'status': 200, 'body': future.result()}, ensure_ascii=False)
        except Exception as error:
            packet = self._encode_error(request_id, error)
        self._packet.emit(page_epoch, packet)

    @Slot(int, str)
    def _deliver(self, page_epoch, packet):
        if not self.closing and page_epoch == self.page_epoch:
            self.response.emit(packet)

    @Slot()
    def publish(self):
        if self.closing or self.state_future and not self.state_future.done():
            return
        self.state_future = self.states.submit(self.service.state)
        self.state_future.add_done_callback(self._publish_result)

    def _publish_result(self, future):
        if self.closing:
            return
        try:
            self._state.emit(json.dumps(future.result(), ensure_ascii=False))
        except Exception:
            logging.exception('State publication failed')

    def suspend(self, new_page=False):
        if self.closing:
            return
        if new_page:
            self.page_epoch += 1
        self.service.invalidate_interaction()
        self.controls.submit(self.service.cancel_jog)
        self.suspended.emit()

    def resume(self):
        if not self.closing:
            self.service.resume()

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.timer.stop()
        self.service.invalidate_interaction()
        self.controls.submit(self.service.cancel_jog)
        def shutdown():
            error = ''
            try:
                for executor in (self.commands, self.controls, self.states):
                    executor.shutdown(wait=True, cancel_futures=True)
                self.service.close()
            except Exception as exc:
                logging.exception('Desktop shutdown failed')
                error = str(exc)
            self._shutdown_done.emit(error)
        Thread(target=shutdown, name='hmi-shutdown', daemon=False).start()
