import json
import time

import pytest
from PySide6.QtCore import QCoreApplication

from backend.service import HmiService
from desktop.bridge import HmiBridge


def spin_until(predicate, timeout=8):
    app = QCoreApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    assert predicate(), 'Qt callback did not arrive'


@pytest.fixture
def bridge(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    service = HmiService(tmp_path / 'simulation.json')
    instance = HmiBridge(service)
    yield instance
    completed = []
    instance.closed.connect(completed.append)
    instance.close()
    spin_until(lambda: completed)
    assert completed == ['']


def test_real_qt_bridge_reports_validation_and_does_not_block_event_loop(bridge):
    replies = []
    bridge.response.connect(lambda value: replies.append(json.loads(value)))
    bridge.request(json.dumps({'id': 'a', 'method': 'POST', 'path': '/api/connect', 'payload': {'mode': 'mock'}}))
    spin_until(lambda: replies)
    assert replies[0]['body']['connected']
    bridge.request(json.dumps({'id': 'b', 'method': 'POST', 'path': '/api/command', 'payload': {'session': 'old', 'code': 20}}))
    spin_until(lambda: len(replies) == 2)
    assert replies[1]['status'] == 409
    bridge.request('invalid json')
    assert replies[-1]['status'] == 422


def test_bridge_stream_and_reload_drop_old_page_reply(bridge):
    from threading import Event
    snapshots = []
    bridge.snapshot.connect(lambda raw: snapshots.append(json.loads(raw)))
    spin_until(lambda: snapshots)
    assert not snapshots[0]['connected']
    replies = []
    bridge.response.connect(replies.append)
    release = Event()
    original = bridge.service.dispatch
    def delayed(*args, **kwargs):
        release.wait(3)
        return original(*args, **kwargs)
    bridge.service.dispatch = delayed
    try:
        bridge.request(json.dumps({'id': 'old', 'method': 'GET', 'path': '/api/state'}))
        bridge.suspend(new_page=True)
    finally:
        release.set()
    spin_until(lambda: not bridge.pending)
    QCoreApplication.processEvents()
    # Responses already queued in Qt must also be invalidated by the page boundary.
    assert not bridge.service.interactive
    assert replies == []


def test_stop_channel_runs_while_normal_requests_wait_for_ack(bridge):
    from threading import Event
    release = Event()
    started = []
    original = bridge.service.dispatch
    def blocking(method, path, payload, **kwargs):
        if path == '/wait':
            started.append(True)
            release.wait(3)
            return {}
        return original(method, path, payload, **kwargs)
    bridge.service.dispatch = blocking
    replies = []
    bridge.response.connect(lambda raw: replies.append(json.loads(raw)))
    try:
        for index in range(4):
            bridge.request(json.dumps({'id': str(index), 'method': 'POST', 'path': '/wait'}))
        spin_until(lambda: len(started) == 4)
        bridge.request(json.dumps({'id': 'stop', 'method': 'POST', 'path': '/api/jog/stop',
                                  'payload': {'session': 'old', 'token': 'press'}}))
        spin_until(lambda: any(p['id'] == 'stop' for p in replies))
        assert not release.is_set()
        assert next(p for p in replies if p['id'] == 'stop')['status'] == 409
    finally:
        release.set()
