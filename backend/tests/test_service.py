import pytest
from fastapi import HTTPException

from backend.service import HmiService


@pytest.fixture
def service(tmp_path):
    instance = HmiService(tmp_path / 'simulation.json')
    yield instance
    instance.close()


def test_native_service_connect_edit_and_session_validation(service):
    assert not service.dispatch('GET', '/api/state', {})['connected']
    state = service.dispatch('POST', '/api/connect', {'mode': 'mock'})
    session = state['session']
    result = service.dispatch('POST', '/api/name', {
        'session': session, 'object_type': 1, 'object_index': 0, 'name': '桌面轴'})
    assert result['ok']
    assert service.state()['axes'][0]['name'] == '桌面轴'
    with pytest.raises(HTTPException) as error:
        service.dispatch('POST', '/api/command', {'code': 20, 'session': 'old'})
    assert error.value.status_code == 409


def test_native_boundary_rejects_unregistered_calls_and_invalid_payload(service):
    with pytest.raises(HTTPException):
        service.dispatch('POST', '/api/private', {})
    with pytest.raises(ValueError):
        service.dispatch('POST', '/api/connect', {'mode': 'wrong'})
    with pytest.raises(HTTPException):
        service.dispatch('GET', '/api/connect', {})


def test_suspend_cancels_jog_and_rejects_late_start_until_resume(service):
    state = service.dispatch('POST', '/api/connect', {'mode': 'mock'})
    session = state['session']
    service.dispatch('POST', '/api/command', {
        'code': 20, 'object_type': 1, 'object_index': 0, 'session': session})
    payload = {'axis': 0, 'direction': 1, 'token': 'press', 'session': session}
    service.dispatch('POST', '/api/jog/start', payload)
    service.suspend()
    assert service.host.worker.jog is None
    with pytest.raises(HTTPException):
        service.dispatch('POST', '/api/jog/start', payload)
    with pytest.raises(HTTPException):
        service.dispatch('POST', '/api/jog/renew', {'token': 'press', 'session': session})
    service.resume()
    # A new press is required; resume never restores the old lease.
    assert service.host.worker.jog is None


def test_close_stops_worker_and_never_reopens(service):
    service.dispatch('POST', '/api/connect', {'mode': 'mock'})
    worker = service.host.worker
    service.close()
    assert not worker.thread.is_alive()
    assert not service.state()['connected']
    with pytest.raises(HTTPException):
        service.dispatch('POST', '/api/connect', {'mode': 'mock'})


def test_old_queued_jog_cannot_start_after_window_resume(service):
    state = service.dispatch('POST', '/api/connect', {'mode': 'mock'})
    epoch = service.interaction_epoch
    service.suspend()
    service.resume()
    with pytest.raises(HTTPException):
        service.dispatch('POST', '/api/jog/start', {
            'axis': 0, 'direction': 1, 'token': 'old-press', 'session': state['session']},
            interaction_epoch=epoch)
    assert service.host.worker.jog is None
