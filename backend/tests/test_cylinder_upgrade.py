"""Deterministic offline cylinder contract checks; no PLC/hardware claims."""
import json
import pytest

from backend.mock_plc import MockPlc, CYLINDER_FIELDS


def cylinder(mode=3, sensors=False):
    plc = MockPlc()
    plc.configured, plc.reset_required = True, False
    plc.cylinders[0]["config"].update(wiring_flags=mode, home_y=1 if mode in (1, 3) else 65535,
        move_x=0 if sensors else 65535, home_x=1 if sensors else 65535,
        delay_ms=200, home_delay_ms=400, timeout_ms=1000)
    return plc


def test_cylinder_requires_real_confirmation_and_reset_sequence():
    from test_mock_behavior import configure
    plc = MockPlc()
    assert plc.command(40, 2, 0)["result"] == 11
    assert plc.command(52, a=plc.config_epoch)["result"] == 18
    configure(plc)
    assert plc.command(52, a=plc.config_epoch)["result"] == 0
    assert plc.command(40, 2, 0)["result"] == 11
    assert plc.command(1)["result"] == 0
    assert plc.command(40, 2, 0)["result"] == 0
    assert plc.command(40, 2, 0)["result"] == 10
    assert plc.command(41, 2, 0)["result"] == 10
    assert plc.command(42, 2, 0)["result"] == 0
    assert plc.command(41, 2, 0)["result"] == 0


@pytest.mark.parametrize("offline,alarm", [(True, False), (False, True), (True, True)])
def test_cylinder_parameter_write_allowed_with_module_fault(offline, alarm):
    plc = cylinder()
    plc.cylinders[0].update(online=not offline, alarm=alarm)
    cfg = dict(plc.cylinders[0]["config"], home_delay_ms=450)
    assert plc.command(50, 2, 0, a=4, staging=[cfg[k] for k in CYLINDER_FIELDS])["result"] == 0
    assert plc.cylinders[0]["config"]["home_delay_ms"] == 450
    assert plc.cylinders[0]["alarm"] is alarm
    assert not plc.configured and plc.reset_required


@pytest.mark.parametrize("changes,expected", [
    ({"resetting": True, "paused": True}, 8),
    ({"paused": True}, 7), ({"manual": False}, 7),
    ({"reset_required": True, "configured": False}, 11),
    ({"reset_required": False, "configured": False}, 14),
    ({"running": True}, 0),
])
def test_cylinder_rejection_order_matches_plc(changes, expected):
    plc = cylinder()
    for key, value in changes.items():
        setattr(plc, key, value)
    assert plc.command(40, 2, 0)["result"] == expected
    assert state(plc)["reason"] == (10 if expected == 0 else expected)


def state(plc):
    return plc.snapshot()["cylinders"][0]


@pytest.mark.parametrize("mode", range(4))
def test_no_sensor_independent_delays_and_output_modes(mode):
    plc = cylinder(mode)
    assert not state(plc)["home"] and not state(plc)["move"]
    original_inputs = plc.snapshot()["io"]["x"]
    assert plc.command(40, 2, 0)["result"] == 0
    plc.tick(.199)
    assert state(plc)["moving"] and not state(plc)["move"]
    plc.tick(.001)
    assert state(plc)["move"] and not state(plc)["moving"]
    assert plc.snapshot()["io"]["y"][:2] == [True, False]
    assert plc.snapshot()["io"]["x"] == original_inputs
    plc.command(41, 2, 0)
    assert not state(plc)["move"]
    assert plc.snapshot()["io"]["y"][:2] == [False, mode in (1, 3)]
    plc.tick(.399)
    assert not state(plc)["home"]
    plc.tick(.001)
    assert state(plc)["home"]
    assert plc.snapshot()["io"]["y"][:2] == [False, mode == 1]
    plc.command(42, 2, 0)
    plc.tick(10)
    assert not state(plc)["home"] and not state(plc)["move"]
    assert not any(plc.snapshot()["io"]["y"])


@pytest.mark.parametrize("inverted", [False, True])
def test_sensor_continuous_confirmation_and_bounce(inverted):
    plc = cylinder(sensors=True)
    plc.cylinders[0]["config"]["wiring_flags"] |= 4 if inverted else 0
    plc.set_cylinder_sensor(0, "move", inverted)
    plc.command(40, 2, 0)
    plc.tick(.1)
    assert not state(plc)["move"]
    plc.set_cylinder_sensor(0, "move", not inverted)
    assert plc.snapshot()["io"]["x"][0] is (not inverted)
    plc.tick(.199)
    assert not state(plc)["move"]
    plc.set_cylinder_sensor(0, "move", inverted)
    plc.tick(.001)
    plc.set_cylinder_sensor(0, "move", not inverted)
    plc.tick(.199)
    assert not state(plc)["move"]
    plc.tick(.001)
    assert state(plc)["move"] and not state(plc)["moving"]
    plc.set_cylinder_sensor(0, "move", inverted)
    assert not state(plc)["move"]


def test_sensor_raw_precedes_confirmation_and_home_delay_is_independent():
    plc = cylinder(sensors=True)
    plc.command(40, 2, 0)
    plc.tick(.3)
    assert plc.snapshot()["io"]["x"][0]
    assert not state(plc)["move"]
    plc.tick(.2)
    assert state(plc)["move"]
    plc.command(41, 2, 0)
    plc.tick(.699)
    assert not state(plc)["home"]
    plc.tick(.001)
    assert state(plc)["home"]


def test_reverse_clears_timed_completion_and_restarts_timer():
    plc = cylinder()
    plc.command(40, 2, 0)
    plc.tick(.15)
    assert plc.command(41, 2, 0)["result"] == 10
    assert plc.command(42, 2, 0)["result"] == 0
    assert plc.command(41, 2, 0)["result"] == 0
    plc.tick(.25)
    assert state(plc)["moving"] and not state(plc)["home"]
    plc.command(42, 2, 0)
    plc.tick(2)
    assert not state(plc)["home"] and not state(plc)["move"]


@pytest.mark.parametrize("step", [.001, 2])
def test_timeout_latches_until_explicit_cancel(step):
    plc = cylinder(sensors=True)
    plc.set_cylinder_sensor(0, "move", False)
    plc.command(40, 2, 0)
    for _ in range(round(2 / step)):
        plc.tick(step)
    assert state(plc)["alarm"]
    assert not any(plc.snapshot()["io"]["y"])
    plc.tick(5)
    assert plc.command(40, 2, 0)["result"] == 17
    plc.cylinders[0]["online"] = False
    plc.command(42, 2, 0)
    assert state(plc)["alarm"]
    plc.cylinders[0]["online"] = True
    plc.command(42, 2, 0)
    assert not state(plc)["alarm"] and not state(plc)["moving"]


@pytest.mark.parametrize("delay,expected", [(699, False), (700, True)])
def test_timeout_wins_exact_tie_and_large_ticks_preserve_order(delay, expected):
    plc = cylinder(sensors=True)
    plc.cylinders[0]["config"]["delay_ms"] = delay
    plc.command(40, 2, 0)
    plc.tick(10)
    assert state(plc)["alarm"] is expected


@pytest.mark.parametrize("mode", [1, 2, 3])
def test_pause_preserves_clamp_but_cancels_completion_and_break_vacuum(mode):
    plc = cylinder(mode)
    plc.command(40, 2, 0)
    plc.tick(.2)
    plc.running, plc.configured, plc.reset_required = True, True, False
    assert plc.command(3)["result"] == 0
    assert plc.snapshot()["io"]["y"][0]
    assert not state(plc)["move"]
    plc.command(4)
    plc.tick(2)
    assert not state(plc)["move"]
    plc.running = False
    plc.command(41, 2, 0)
    plc.running = True
    plc.command(3)
    assert plc.snapshot()["io"]["y"][1] is (mode == 1)


@pytest.mark.parametrize("field,value", [("delay_ms", 0), ("home_delay_ms", 0),
    ("delay_ms", 1000), ("home_delay_ms", 1000), ("timeout_ms", 0),
    ("wiring_flags", 16), ("move_x", 128)])
def test_invalid_config_is_rejected_atomically(field, value):
    plc = cylinder()
    cfg = dict(plc.cylinders[0]["config"])
    changed = dict(cfg, **{field: value})
    words = [changed[key] for key in CYLINDER_FIELDS]
    assert plc.command(50, 2, 0, a=7, staging=words)["result"] == 9
    assert plc.cylinders[0]["config"] == cfg


@pytest.mark.parametrize("source", ["connected", "online", "handshake", "cylinder_online"])
def test_connection_loss_cancels_request_and_never_replays(source):
    plc = cylinder()
    plc.command(40, 2, 0)
    plc.tick(.1)
    if source == "cylinder_online":
        plc.cylinders[0]["online"] = False
    else:
        setattr(plc, source, False)
    plc.tick(.1)
    assert not state(plc)["moving"] and not state(plc)["move"]
    assert plc.snapshot()["io"]["y"][0] is (source != "cylinder_online")
    if source == "cylinder_online":
        plc.cylinders[0]["online"] = True
    else:
        setattr(plc, source, True)
    plc.tick(2)
    assert not state(plc)["move"]


def test_disconnect_stops_break_vacuum_output():
    plc = cylinder(3)
    plc.command(41, 2, 0)
    assert plc.snapshot()["io"]["y"][1]
    plc.connected = False
    plc.tick(.1)
    assert not any(plc.snapshot()["io"]["y"])
    assert not state(plc)["moving"] and not state(plc)["home"]


def test_delay_edit_after_completion_preserves_output_and_applies_next_request():
    plc = cylinder()
    plc.command(40, 2, 0)
    plc.tick(.2)
    cfg = dict(plc.cylinders[0]["config"], delay_ms=600)
    assert plc.command(50, 2, 0, a=1, staging=[cfg[k] for k in CYLINDER_FIELDS])["result"] == 0
    plc.tick(2)
    assert state(plc)["move"] and not state(plc)["alarm"]
    assert plc.snapshot()["io"]["y"][0]
    assert plc.command(40, 2, 0)["result"] == 11
    plc.configured, plc.reset_required = True, False
    plc.command(40, 2, 0)
    plc.tick(.599)
    assert not state(plc)["move"]
    plc.tick(.001)
    assert state(plc)["move"]


@pytest.mark.parametrize("mode", [1, 3])
def test_two_output_mode_requires_home_output_before_action(mode):
    plc = cylinder(mode)
    plc.cylinders[0]["config"]["home_y"] = 65535
    assert plc.command(40, 2, 0)["result"] == 14
    assert plc.command(41, 2, 0)["result"] == 14
    assert not any(plc.snapshot()["io"]["y"])


def test_mode_switch_cancels_timed_completion_without_replay():
    plc = cylinder()
    plc.command(40, 2, 0)
    plc.manual = False
    plc.tick(2)
    assert not state(plc)["move"] and not state(plc)["moving"]
    assert plc.snapshot()["io"]["y"][0]
    plc.manual = True
    plc.tick(2)
    assert not state(plc)["move"]


def test_unbound_has_no_raw_input_or_output():
    plc = cylinder()
    plc.bound_cylinders = 0
    assert plc.command(40, 2, 0)["result"] == 4
    plc.tick(2)
    assert not any(plc.snapshot()["io"]["x"])
    assert not any(plc.snapshot()["io"]["y"])


def test_transport_rejects_invalid_cylinder_config_and_summary():
    from backend.plc_transport import PlcTransport
    from backend.xj_protocol import STATUS_OFFSET
    from test_transport_review import RegisterPeer
    peer = RegisterPeer()
    status = peer.input[:104]
    status[STATUS_OFFSET["cylinder_bound"] + 3] = 1
    config = {name: peer.input[base:base + size] for name, base, size in
              (("axis_config", 542, 256), ("cylinder_config", 798, 432), ("points", 1230, 600))}
    valid = [3, 0, 1, 65535, 65535, 200, 1000, 400]
    config["cylinder_config"][:8] = valid
    PlcTransport._validate_config(config, status)
    for offset, value in ((0, 16), (1, 65535), (2, 65535), (3, 128), (5, 0), (7, 0), (7, 1000)):
        config["cylinder_config"][:8] = valid
        config["cylinder_config"][offset] = value
        with pytest.raises(ValueError):
            PlcTransport._validate_config(config, status)
    status[STATUS_OFFSET["cylinder_summary"]] = 16
    with pytest.raises(ValueError):
        PlcTransport._validate_status(status)


def test_legacy_persistence_preserves_axis_points_and_migrates_delay(tmp_path):
    path = tmp_path / "simulation.json"
    plc = MockPlc(path)
    plc.axes[0]["config"]["manual_speed"] = 123
    plc.points[0].update(position=12.5, taught=True)
    plc.close()
    data = json.loads(path.read_text())
    data["signature"] = 0x584A5632
    for item in data["cylinders"]:
        item["config"].pop("home_delay_ms")
        item["config"]["flags"] = 0
    path.write_text(json.dumps(data))
    restored = MockPlc(path)
    assert restored.persistence_error is None
    assert restored.axes[0]["config"]["manual_speed"] == 123
    assert restored.points[0]["position"] == 12.5
    assert restored.cylinders[0]["config"]["home_delay_ms"] == 200
    assert not restored.configured and restored.reset_required
    data["cylinders"][0]["config"]["flags"] = 1
    path.write_text(json.dumps(data))
    assert MockPlc(path).persistence_error
