"""Deterministic latency model; not PLC compiler or machine acceptance."""
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.plc_transport import PlcTransport, SnapshotUnavailable
from backend.tests.test_transport_review import RegisterPeer
from backend.xj_protocol import address


def exercise(period_ms, phase_ms):
    peer = RegisterPeer()
    transport = PlcTransport('127.0.0.1')
    transport.client = peer
    clock = [phase_ms / 1000]
    original = peer.read_input

    def read(base, count):
        clock[0] += .020
        epoch = 2 * (int(round(clock[0] * 1000)) // period_ms + 1)
        peer.input[address('status', 'snapshot_epoch')] = epoch
        # Every live record carries the publication identity.
        peer.input[address('axis_live')] = epoch
        peer.input[address('cylinder_live')] = epoch
        return original(base, count)

    peer.read_input = read
    with patch('backend.plc_transport.time.monotonic', side_effect=lambda: clock[0]), \
         patch('backend.plc_transport.time.sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)):
        data = transport._coherent(('status', 'axis_live', 'cylinder_live', 'io'))
    epoch = data['status'][103]
    assert data['axis_live'][0] == data['cylinder_live'][0] == epoch
    assert all(c[0] == 'read' for c in peer.calls)
    assert clock[0] - phase_ms / 1000 < 1


def test_reproduces_100ms_publication_starvation():
    with pytest.raises(SnapshotUnavailable):
        exercise(100, 0)


@pytest.mark.parametrize('phase_ms', range(0, 300, 5))
def test_delivered_publication_allows_coherent_reads_at_20ms_latency(phase_ms):
    source = (Path(__file__).parents[2] / 'plc/src/03_pou/功能块_服务端.st').read_text(encoding='utf-8-sig')
    period = int(re.search(r'tmr发布[(]IN := NOT tmr发布.Q, PT := T#([0-9]+)ms[)]', source)[1])
    exercise(period, phase_ms)
