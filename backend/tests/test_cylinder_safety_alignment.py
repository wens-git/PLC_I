"""Offline checks for output retention and engineering IO validation."""
import json
import pytest
from backend.mock_plc import MockPlc
from test_cylinder_upgrade import cylinder, state


@pytest.mark.parametrize('enabled', [False, True])
def test_axis_fault_reset_requires_explicit_enable(enabled):
    plc = MockPlc()
    plc.axes[0].update(enabled=enabled, alarm=True, alarm_code=2100, drive_error=1)
    assert plc.command(23, 1, 0)['result'] == 0
    assert not plc.axes[0]['enabled'] and not plc.axes[0]['alarm']
    assert plc.command(27, 1, 0, a=1000, b=1000)['result'] == 6
    assert plc.command(20, 1, 0)['result'] == 0
    assert plc.command(27, 1, 0, a=1000, b=1000)['result'] == 0


@pytest.mark.parametrize('mode', range(4))
@pytest.mark.parametrize('code', [40, 41])
def test_timeout_preserves_only_vacuum_outputs_until_explicit_cancel(mode, code):
    plc = cylinder(mode, sensors=True)
    side = 'move' if code == 40 else 'home'
    plc.set_cylinder_sensor(0, side, False)
    assert plc.command(code, 2, 0)['result'] == 0
    before = plc.snapshot()['io']['y']
    plc.tick(1)
    assert state(plc)['alarm_code'] == 2140
    assert not state(plc)['moving']
    expected = before if mode in (2, 3) else [False] * 56
    assert plc.snapshot()['io']['y'] == expected
    plc.tick(100)
    assert plc.snapshot()['io']['y'] == expected
    assert plc.command(code, 2, 0)['result'] == 17
    assert plc.command(42, 2, 0)['result'] == 0
    assert not any(plc.snapshot()['io']['y'])
    assert not state(plc)['alarm']
    plc.tick(100)
    assert not state(plc)['moving']


@pytest.mark.parametrize('mode', range(4))
def test_cancel_clears_electrical_outputs_and_time_completion(mode):
    plc = cylinder(mode)
    plc.command(40, 2, 0)
    plc.tick(.2)
    assert state(plc)['move']
    plc.command(42, 2, 0)
    assert not any(plc.snapshot()['io']['y'])
    assert not state(plc)['move'] and not state(plc)['home']
    # Electrical deenergization is not a physical valve-position simulation.
    plc.tick(10)
    assert not state(plc)['move'] and not state(plc)['home']


@pytest.mark.parametrize('key,boundary', [('move_x', 112), ('home_x', 112), ('move_y', 56), ('home_y', 56)])
def test_capacity_edges(key, boundary):
    plc = cylinder(3, sensors=True)
    plc.cylinders[0]['config'][key] = boundary
    assert plc.command(40, 2, 0)['result'] == 9
    plc.cylinders[0]['config'][key] = boundary - 1
    assert plc.command(40, 2, 0)['result'] == 0
    assert len(plc.snapshot()['io']['x']) == 112
    assert len(plc.snapshot()['io']['y']) == 56


@pytest.mark.parametrize('side', ['move_x', 'home_x'])
def test_cross_cylinder_sensor_collision_is_rejected(side):
    plc = cylinder(3, sensors=True)
    plc.cylinders[0]['config'][side] = plc.cylinders[1]['config']['home_x']
    assert plc.command(40, 2, 0)['result'] == 9
    plc.bound_cylinders &= ~(1 << 1)
    assert plc.command(40, 2, 0)['result'] == 0


def test_transport_rejects_capacity_and_cross_cylinder_inputs():
    from backend.plc_transport import PlcTransport
    from backend.xj_protocol import STATUS_OFFSET
    from test_transport_review import RegisterPeer
    peer = RegisterPeer()
    status = peer.input[:104]
    status[STATUS_OFFSET['cylinder_bound'] + 3] = 3
    config = {name: peer.input[base:base + size] for name, base, size in
              (('axis_config', 542, 256), ('cylinder_config', 798, 432), ('points', 1230, 600))}
    valid = [3, 0, 1, 0, 1, 200, 1000, 400, 3, 2, 3, 110, 111, 200, 1000, 400]
    config['cylinder_config'][:16] = valid
    PlcTransport._validate_config(config, status)
    for offset, value in ((11, 1), (12, 0), (11, 112), (9, 56)):
        config['cylinder_config'][:16] = valid
        config['cylinder_config'][offset] = value
        with pytest.raises(ValueError):
            PlcTransport._validate_config(config, status)


@pytest.mark.parametrize('signature', [0x584A5632, 0x584A5633])
def test_previous_unbound_default_wiring_migrates_without_axis_loss(tmp_path, signature):
    path = tmp_path / 'previous.json'
    plc = MockPlc(path)
    plc.axes[0]['config']['manual_speed'] = 123
    plc.points[0].update(position=17, taught=True)
    plc.close()
    data = json.loads(path.read_text())
    data['signature'] = signature
    for index, item in enumerate(data['cylinders']):
        cfg = item['config']
        if index >= 12:
            cfg.update(move_y=index * 2, home_y=index * 2 + 1,
                       move_x=index * 2, home_x=index * 2 + 1, home_delay_ms=0)
        if signature == 0x584A5632:
            cfg.pop('home_delay_ms')
            cfg['flags'] = 0
    path.write_text(json.dumps(data))
    loaded = MockPlc(path)
    assert loaded.persistence_error is None
    assert loaded.axes[0]['config']['manual_speed'] == 123
    assert loaded.points[0]['position'] == 17
    assert loaded.cylinders[53]['config']['move_y'] == 65535
    assert not loaded.configured and loaded.reset_required
