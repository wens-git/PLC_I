"""Offline simulator checks; these are not PLC or real-machine acceptance."""
import copy
import json

import pytest

from backend.mock_plc import MockPlc


def pair(value):
    return [(value >> 16) & 65535, value & 65535]


def test_software_estop_release_clears_only_latch():
    plc = MockPlc()
    assert plc.command(10)['result'] == 0
    before = copy.deepcopy(plc.axes)
    assert plc.command(11)['result'] == 0
    assert not plc.software_estop
    assert not plc.running
    assert plc.axes == before
    plc.software_estop = True
    plc.estop = True
    assert plc.command(11)['result'] == 3
    assert plc.software_estop


def axis_record(**changes):
    values = dict(positive_limit=1000000, negative_limit=-1000000,
                  manual_speed=40000, auto_speed=60000, acceleration=100000,
                  deceleration=100000, estop_deceleration=200000, flags=1)
    values.update(changes)
    words = []
    for key, value in values.items():
        words.extend([value] if key == "flags" else pair(value))
    return words + [0]


def enabled():
    plc = MockPlc()
    assert plc.command(20, 1, 0)["result"] == 0
    return plc


def test_zero_requires_enabled_axis_and_reset_rejects_motion():
    plc = MockPlc()
    assert plc.command(30, 1, 0)["result"] == 6
    assert plc.command(20, 1, 0)["result"] == 0
    assert plc.command(30, 1, 0)["result"] == 0
    assert plc.command(24, 1, 0)["result"] == 0
    assert plc.command(23, 1, 0)["result"] == 10


def test_safe_defaults_and_pure_detached_snapshot():
    plc = MockPlc()
    first = plc.snapshot()
    assert first == plc.snapshot()
    assert first["flow_ready"] and not first["configured"]
    assert not first["running"] and not first["paused"]
    assert first["features"] == 0 and first["ack_object"] == 0
    assert sum(a["bound"] for a in first["axes"]) == 3
    assert sum(c["bound"] for c in first["cylinders"]) == 12
    assert all(a["permit"] == 0 and a["reason"] == 4 for a in first["axes"][3:])
    first["axes"][0]["config"]["manual_speed"] = -1
    first["axes"][0]["points"][0]["position"] = 999
    assert plc.snapshot()["axes"][0]["config"]["manual_speed"] > 0
    assert plc.snapshot()["axes"][0]["points"][0]["position"] != 999
    assert "name" not in first["axes"][0]  # names are host-owned since 1.2


def test_ack_duplicate_rejection_and_wrap():
    plc = enabled()
    result = plc.command(28, 1, 0, a=10000, b=1000, sequence=123)
    assert result["result"] == 0 and result["seq"] == 123
    assert plc.command(10, sequence=123) == result
    assert not plc.snapshot()["estop"]
    plc.tick(10)
    assert plc.snapshot()["axes"][0]["position"] == 10
    plc.ack_epoch = 65535
    rejected = plc.command(27, 1, 7, a=100, b=1000, sequence=124)
    assert rejected["result"] == 4 and rejected["ack_epoch"] == 0
    state = plc.snapshot()
    assert (state["ack_seq"], state["ack_result"], state["ack_object"]) == (124, 4, 263)
    assert plc.command(9, sequence=65535)["result"] == 0
    assert plc.command(9)["seq"] == 1


@pytest.mark.parametrize("code,kind,index,result", [
    (26, 1, -1, 15), (26, 1, 16, 15), (42, 2, 54, 15),
    (42, 2, -1, 15), (10, 0, 1, 15), (9, 1, 0, 15),
    (20, 2, 0, 15), (40, 1, 0, 15), (26, 1, 3, 4),
    (42, 2, 12, 4), (51, 3, 0, 14), (51, 1, 0, 14),
    (99, 0, 0, 14), (53, 0, 0, 14), (2, 0, 0, 11),
    (3, 0, 0, 11), (4, 0, 0, 11),
])
def test_invalid_objects_stops_and_unimplemented_flows(code, kind, index, result):
    assert MockPlc().command(code, kind, index)["result"] == result


@pytest.mark.parametrize("code,args", [(22, {}), (24, {}), (25, {}),
    (27, dict(a=1000, b=1000)), (28, dict(a=1000, b=1000)), (29, dict(a=0))])
def test_motion_requires_enable(code, args):
    assert MockPlc().command(code, 1, 0, **args)["result"] == 6


def test_timed_moves_stop_disable_home_and_zero():
    plc = enabled()
    assert plc.command(27, 1, 0, a=10000, b=2000)["result"] == 0
    assert plc.command(28, 1, 0, a=1000, b=1000)["result"] == 10
    assert plc.command(30, 1, 0)["result"] == 10
    plc.tick(2)
    assert plc.snapshot()["axes"][0]["position"] == 4
    assert plc.command(21, 1, 0)["result"] == 0
    plc.tick(10)
    assert plc.snapshot()["axes"][0]["position"] == 4
    plc.command(20, 1, 0)
    plc.command(22, 1, 0)
    assert not plc.snapshot()["axes"][0]["homed"]
    plc.tick(1)
    assert plc.snapshot()["axes"][0]["homed"]
    assert plc.command(30, 1, 0)["result"] == 0
    assert not plc.snapshot()["axes"][0]["homed"]
    plc.axes[0].update(alarm=True, alarm_code=17)
    assert plc.command(23, 1, 0)["result"] == 0
    assert not plc.snapshot()["axes"][0]["alarm"]


@pytest.mark.parametrize("stop", [9, 10])
def test_global_stop_and_estop_cancel_every_motion(stop):
    plc = enabled()
    plc.command(27, 1, 0, a=10000, b=1000)
    plc.command(40, 2, 0)
    plc.command(stop)
    before = plc.snapshot()
    plc.tick(10)
    state = plc.snapshot()
    assert state["axes"][0]["position"] == before["axes"][0]["position"]
    assert not state["axes"][0]["running"] and not state["cylinders"][0]["moving"]
    if stop == 10:
        assert plc.command(40, 2, 0)["result"] == 3
        assert plc.command(24, 1, 0)["result"] == 3
        assert plc.command(1)["result"] == 3
        plc.estop = True
        assert plc.command(11)["result"] == 3
        plc.estop = False
        assert plc.command(11)["result"] == 0
        assert not plc.snapshot()["axes"][0]["running"]


def test_stop_bypasses_ordinary_permissions():
    plc = enabled()
    plc.command(24, 1, 0)
    plc.online = False
    plc.manual = False
    plc.axes[0]["alarm"] = True
    assert plc.command(26, 1, 0)["result"] == 0
    assert plc.command(42, 2, 0)["result"] == 0
    assert plc.command(9)["result"] == 0


def test_jog_lease_is_independent_and_bound_to_sequence_counter_object():
    plc = enabled()
    plc.command(24, 1, 0, sequence=30)
    plc.tick(1)
    assert not plc.renew_jog(0x101, 30, 1)
    assert not plc.renew_jog(0x100, 29, 1)
    assert plc.renew_jog(0x100, 30, 1)
    plc.tick(1)
    assert not plc.renew_jog(0x100, 30, 1)
    plc.tick(0.5)
    axis = plc.snapshot()["axes"][0]
    assert not axis["running"] and axis["position"] == 100
    assert not plc.renew_jog(0x100, 30, 2)
    plc.command(25, 1, 0, sequence=31)
    plc.tick(0.2)
    assert plc.snapshot()["axes"][0]["velocity"] < 0
    plc.command(26, 1, 0)
    assert not plc.renew_jog(0x100, 31, 3)


def test_one_jog_limit_and_offline_revoke():
    plc = enabled()
    plc.command(20, 1, 1)
    plc.command(24, 1, 0)
    assert plc.command(25, 1, 1)["result"] == 10
    plc.online = False
    plc.tick(0.1)
    assert not plc.snapshot()["axes"][0]["running"]
    plc.online = True
    plc.axes[0]["position"] = 999
    plc.command(24, 1, 0)
    plc.tick(1)
    assert plc.snapshot()["axes"][0]["position"] == 1000
    assert not plc.snapshot()["axes"][0]["running"]
    assert plc.command(24, 1, 0)["result"] == 17
    assert plc.command(25, 1, 0)["result"] == 0


@pytest.mark.parametrize("args", [dict(a=1000001, b=1000), dict(a=0, b=0),
    dict(a=0, b=-1), dict(a=2**31, b=1000), dict(a=0, b=2**31),
    dict(a=0, b=1000, c=1), dict(a=0.5, b=1000)])
def test_invalid_motion_parameters(args):
    assert enabled().command(27, 1, 0, **args)["result"] == 9


def test_relative_overflow():
    plc = enabled()
    plc.axes[0]["config"]["flags"] = 0
    plc.axes[0]["position"] = 2147483.647
    assert plc.command(28, 1, 0, a=1, b=1000)["result"] == 9


def test_cylinder_timing_and_cancel():
    plc = MockPlc()
    configure(plc)
    assert plc.command(52, a=plc.config_epoch)["result"] == 0
    assert plc.command(1)["result"] == 0
    assert plc.command(40, 2, 0)["result"] == 0
    assert plc.command(41, 2, 0)["result"] == 10
    assert plc.command(40, 2, 0)["result"] == 10
    plc.tick(0.1)
    assert plc.snapshot()["cylinders"][0]["moving"]
    plc.tick(1)
    assert plc.snapshot()["cylinders"][0]["move"]
    assert plc.command(41, 2, 0)["result"] == 0
    plc.tick(1)
    assert plc.snapshot()["cylinders"][0]["home"]
    plc.command(40, 2, 0)
    assert plc.command(42, 2, 0)["result"] == 0
    assert not any(plc.snapshot()["io"]["y"])


def test_point_teach_enable_execute_and_epoch():
    plc = enabled()
    assert plc.command(29, 1, 0, a=0)["result"] == 18
    assert plc.command(31, 1, 0, a=0, b=-5000, c=2000)["result"] == 0
    point = plc.snapshot()["axes"][0]["points"][0]
    assert (point["position"], point["speed"], point["taught"], point["enabled"]) == (-5, 2, True, False)
    assert plc.command(29, 1, 0, a=0)["result"] == 18
    assert plc.command(50, 3, 0, a=4, b=1, staging=pair(-5000) + pair(2000) + [3])["result"] == 0
    assert plc.command(29, 1, 0, a=0)["result"] == 0
    plc.tick(3)
    assert plc.snapshot()["axes"][0]["position"] == -5
    assert plc.command(31, 1, 0, a=120, b=0, c=1000)["result"] == 9
    assert plc.command(31, 1, 1, a=0, b=0, c=1000)["result"] == 18


def test_point_pool_claim_release_and_owner_rules():
    plc = enabled()
    assert plc.command(31, 1, 0, a=20, b=1000, c=1000)["result"] == 0
    state = plc.snapshot()
    assert state["axes"][0]["points"][-1]["index"] == 20
    assert state["points"][20]["owner"] == 0
    assert plc.command(31, 1, 1, a=20, b=0, c=1000)["result"] == 18
    # Enable the taught point: release is refused while enabled.
    assert plc.command(50, 3, 20, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [3])["result"] == 0
    assert plc.command(50, 3, 20, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 9
    # Disabled but taught: release succeeds and clears the taught record.
    assert plc.command(50, 3, 20, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [2])["result"] == 0
    assert plc.command(50, 3, 20, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 0
    released = plc.snapshot()["points"][20]
    assert released["owner"] is None and not released["taught"] and not released["enabled"]
    # The freed slot can be claimed again by another axis via teaching.
    assert plc.command(20, 1, 1)["result"] == 0
    assert plc.command(31, 1, 1, a=20, b=0, c=1000)["result"] == 0
    assert plc.snapshot()["points"][20]["owner"] == 1
    # Claim via code 50 (untaught) and release it again.
    assert plc.command(50, 3, 21, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [4])["result"] == 0
    assert plc.snapshot()["points"][21]["owner"] == 1
    assert plc.command(29, 1, 1, a=21)["result"] == 18
    assert plc.command(50, 3, 21, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 0
    assert plc.snapshot()["points"][21]["owner"] is None
    # Releasing an already free slot is rejected.
    assert plc.command(50, 3, 22, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 9
    # Taught bit still cannot be forged or cleared by a non-release write.
    assert plc.command(50, 3, 20, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [1 << 2])["result"] == 9


def test_axis_parameter_mask_atomicity_and_epoch():
    plc = MockPlc()
    original = copy.deepcopy(plc.snapshot()["axes"][0]["config"])
    assert plc.command(50, 1, 0, a=1, b=0, staging=axis_record(positive_limit=-2000000))["result"] == 9
    assert plc.snapshot()["axes"][0]["config"] == original
    assert plc.command(50, 1, 0, a=4, b=1, staging=axis_record(manual_speed=1000))["result"] == 16
    assert plc.command(50, 1, 0, a=4, b=0, staging=axis_record(manual_speed=1000, auto_speed=9999))["result"] == 0
    config = plc.snapshot()["axes"][0]["config"]
    assert config["manual_speed"] == 1 and config["auto_speed"] == original["auto_speed"]
    assert plc.snapshot()["config_epoch"] == 1
    for mask in (0, 256):
        assert plc.command(50, 1, 0, a=mask, b=1, staging=axis_record())["result"] == 9
    bad = axis_record()
    bad[15] = 1
    assert plc.command(50, 1, 0, a=1, b=1, staging=bad)["result"] == 9


def test_cylinder_parameter_readonly_wiring_and_feature_gate():
    plc = MockPlc()
    cfg = plc.snapshot()["cylinders"][0]["config"]
    words = [cfg[k] for k in ("wiring_flags", "move_y", "home_y", "move_x", "home_x", "delay_ms", "timeout_ms", "home_delay_ms")]
    words[5] = 100
    assert plc.command(50, 2, 0, a=1, b=0, staging=words)["result"] == 0
    words[1] += 1
    assert plc.command(50, 2, 0, a=1, b=1, staging=words)["result"] == 9
    words[1] -= 1
    words[7] = 1
    assert plc.command(50, 2, 0, a=4, b=1, staging=words)["result"] == 0
    assert plc.cylinders[0]["config"]["home_delay_ms"] == 1
    words[7], words[5] = 0, 3000
    assert plc.command(50, 2, 0, a=1, b=2, staging=words)["result"] == 9


def test_retired_name_command_51_is_unsupported_and_changes_nothing():
    plc = MockPlc()
    assert plc.command(51, 1, 0, staging=[65] + [0] * 15)["result"] == 14
    assert plc.config_epoch == 0


def test_axis_15_point_is_distinct_from_free_slot():
    """0x3C used to mean 'free'; in 1.2 it is axis 15 and free is 0x40."""
    plc = MockPlc()
    plc.bound_axes |= 1 << 15
    plc.axes[15]["online"] = True
    state = plc.snapshot()
    assert state["points"][15]["owner"] == 15
    assert state["points"][16]["owner"] is None
    assert plc.command(50, 3, 30, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [15 << 2])["result"] == 0
    assert plc.snapshot()["points"][30]["owner"] == 15
    assert plc.command(50, 3, 30, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 0
    assert plc.snapshot()["points"][30]["owner"] is None
    # The free bit combined with owner/enable bits is never valid.
    assert plc.command(50, 3, 31, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40 | 4])["result"] == 9


def test_point_flags_cannot_forge_teaching():
    plc = MockPlc()
    for flags in (1, 2, 3, 4):
        assert plc.command(50, 3, 0, a=4, staging=pair(0) + pair(1000) + [flags])["result"] == 9


def configure(plc):
    for index in range(3):
        assert plc.command(31, 1, index, a=index, b=0, c=1000)["result"] == 0
        assert plc.command(50, 3, index, a=4, b=plc.config_epoch,
                           staging=pair(0) + pair(1000) + [(index << 2) | 3])["result"] == 0


def test_confirmation_reset_and_invalidation():
    plc = MockPlc()
    assert plc.command(52)["result"] == 18
    configure(plc)
    assert plc.command(52, a=plc.config_epoch)["result"] == 0
    assert plc.snapshot()["configured"] and plc.snapshot()["reset_required"]
    assert plc.command(1)["result"] == 0
    assert not plc.snapshot()["reset_required"]
    assert plc.command(2)["result"] == 0
    assert plc.snapshot()["running"]
    assert plc.command(9)["result"] == 0
    assert not plc.snapshot()["running"] and not plc.snapshot()["paused"]
    assert plc.command(31, 1, 0, a=0, b=1000, c=1000)["result"] == 0
    assert not plc.snapshot()["configured"]


def test_start_pause_resume_flow():
    plc = MockPlc()
    assert plc.command(2)["result"] == 11  # 未确认配置
    configure(plc)
    assert plc.command(52, a=plc.config_epoch)["result"] == 0
    assert plc.command(1)["result"] == 0
    assert plc.command(3)["result"] == 8  # 未运行
    assert plc.command(4)["result"] == 8  # 未暂停
    assert plc.command(2)["result"] == 0
    state = plc.snapshot()
    assert state["running"] and not state["paused"]
    assert plc.command(2)["result"] == 8  # 重复启动
    assert plc.command(3)["result"] == 0
    state = plc.snapshot()
    assert state["paused"] and not state["running"]
    assert plc.command(3)["result"] == 8  # 重复暂停
    assert plc.command(4)["result"] == 0
    state = plc.snapshot()
    assert state["running"] and not state["paused"]
    assert plc.command(10)["result"] == 0
    state = plc.snapshot()
    assert state["estop"] and not state["running"] and not state["paused"]


def test_persistence_only_configuration_and_points(tmp_path):
    path = tmp_path / "isolated-simulation.json"
    plc = MockPlc(persistence_path=path)
    plc.command(31, 1, 0, a=0, b=1250, c=1000)
    plc.command(20, 1, 0)
    plc.command(24, 1, 0)
    plc.tick(0.2)
    plc.close()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["simulation_only"] is True
    assert "name" not in json.dumps(payload)
    reopened = MockPlc(persistence_path=path)
    axis = reopened.snapshot()["axes"][0]
    assert axis["points"][0]["position"] == 1.25
    assert not axis["enabled"] and not axis["running"] and axis["position"] == 0
    assert reopened.config_epoch == 0 and reopened.ack_seq == 0
    assert not reopened.configured and reopened.snapshot()["reset_required"]


def test_tick_rejects_invalid_elapsed_and_advances_fractional_uptime():
    plc = MockPlc()
    for elapsed in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            plc.tick(elapsed)
    for _ in range(10):
        plc.tick(0.1)
    assert plc.snapshot()["uptime"] == 1
    assert plc.snapshot()["heartbeat"] == 5
    assert plc.snapshot()["snapshot_epoch"] % 2 == 0


@pytest.mark.parametrize("bit,key,value,expected", [
    (0, "positive_limit", 2000000, 2000), (1, "negative_limit", -2000000, -2000),
    (2, "manual_speed", 1000, 1), (3, "auto_speed", 2000, 2),
    (4, "acceleration", 3000, 3), (5, "deceleration", 4000, 4),
    (6, "estop_deceleration", 5000, 5), (7, "flags", 0, 0),
])
def test_each_axis_parameter_mask(bit, key, value, expected):
    plc = MockPlc()
    assert plc.command(50, 1, 0, a=1 << bit, staging=axis_record(**{key: value}))["result"] == 0
    assert plc.snapshot()["axes"][0]["config"][key] == expected


def test_point_parameter_position_speed_and_taught_flag_preservation():
    plc = MockPlc()
    plc.command(31, 1, 0, a=0, b=0, c=1000)
    assert plc.command(50, 3, 0, a=3, b=1, staging=pair(-1250) + pair(2000) + [2])["result"] == 0
    point = plc.snapshot()["axes"][0]["points"][0]
    assert point["position"] == -1.25 and point["speed"] == 2 and point["taught"]
    assert plc.command(50, 3, 0, a=4, b=2, staging=pair(-1250) + pair(2000) + [0])["result"] == 9


def test_cylinder_timeout_alarm_edges_and_reset():
    plc = MockPlc()
    cfg = plc.snapshot()["cylinders"][0]["config"]
    words = [cfg[key] for key in ("wiring_flags", "move_y", "home_y", "move_x", "home_x", "delay_ms", "timeout_ms", "home_delay_ms")]
    words[5:7] = [0, 100]
    assert plc.command(50, 2, 0, a=3, staging=words)["result"] == 0
    configure(plc)
    assert plc.command(52, a=plc.config_epoch)["result"] == 0
    assert plc.command(1)["result"] == 0
    assert plc.command(40, 2, 0)["result"] == 0
    plc.tick(1)
    assert plc.snapshot()["cylinders"][0]["alarm"]
    assert plc.snapshot()["alarm_count"] == 1
    assert not any(plc.snapshot()["io"]["y"])
    plc.tick(1)
    assert plc.snapshot()["alarm_count"] == 1
    assert plc.command(40, 2, 0)["result"] == 17
    assert plc.command(1)["result"] == 0
    assert plc.snapshot()["alarms"]
    assert plc.command(42, 2, 0)["result"] == 0
    assert not plc.snapshot()["alarms"]


@pytest.mark.parametrize("fault,result", [("offline", 5), ("alarm", 17), ("mode", 7), ("flow", 8)])
def test_axis_cylinder_permits_follow_command_gate(fault, result):
    plc = enabled()
    if fault == "offline":
        plc.axes[0]["online"] = plc.cylinders[0]["online"] = False
    elif fault == "alarm":
        plc.axes[0]["alarm"] = plc.cylinders[0]["alarm"] = True
    elif fault == "mode":
        plc.manual = False
    else:
        plc.running = True
        plc.resetting = True
    assert plc.command(27, 1, 0, a=1000, b=1000)["result"] == result
    assert plc.command(40, 2, 0)["result"] == result
    state = plc.snapshot()
    assert not state["axes"][0]["permit"] & 64
    assert not state["cylinders"][0]["permit"] & 1


def test_hard_limit_blocks_direction_and_tick_interrupts_motion():
    plc = enabled()
    plc.axes[0]["limits"] = 1
    assert plc.command(27, 1, 0, a=1000, b=1000)["result"] == 17
    assert plc.command(27, 1, 0, a=-1000, b=1000)["result"] == 0
    plc.axes[0]["limits"] = 2
    plc.tick(1)
    assert plc.snapshot()["axes"][0]["position"] == 0
    assert not plc.snapshot()["axes"][0]["running"]


def test_tick_large_step_stops_exactly_at_jog_lease():
    plc = enabled()
    plc.command(24, 1, 0)
    plc.tick(100)
    assert plc.snapshot()["axes"][0]["position"] == 60
    assert not plc.snapshot()["axes"][0]["running"]


@pytest.mark.parametrize("mutation,result", [("limits", 9), ("sensor", 9), ("busy", 10)])
def test_confirmation_rejects_unsafe_configuration(mutation, result):
    plc = MockPlc()
    configure(plc)
    if mutation == "limits":
        plc.axes[0]["config"]["flags"] = 0
    elif mutation == "sensor":
        plc.cylinders[0]["config"]["move_x"] = 65535
        plc.cylinders[0]["config"]["delay_ms"] = 0
    else:
        assert plc.command(52, a=plc.config_epoch)["result"] == 0
        assert plc.command(1)["result"] == 0
        assert plc.command(40, 2, 0)["result"] == 0
    assert plc.command(52, a=plc.config_epoch)["result"] == result
    assert plc.configured is (mutation == "busy")


@pytest.mark.parametrize("content", ["null", "[]", "{}", "broken-json"])
def test_invalid_persistence_is_safe_default(tmp_path, content):
    path = tmp_path / "invalid-simulation.json"
    path.write_text(content, encoding="utf-8")
    plc = MockPlc(persistence_path=path)
    assert plc.persistence_error
    assert not plc.configured and not plc.snapshot()["axes"][0]["enabled"]


def test_persistence_failure_rejects_and_rolls_back(tmp_path, monkeypatch):
    plc = MockPlc(persistence_path=tmp_path / "simulation.json")
    before = plc.snapshot()["axes"][0]["points"]
    def fail():
        raise OSError("disk unavailable")
    monkeypatch.setattr(plc, "_save", fail)
    assert plc.command(31, 1, 0, a=0, b=1234, c=1000)["result"] == 19
    assert plc.config_epoch == 0
    assert plc.snapshot()["axes"][0]["points"] == before


def test_signature_and_nonzero_unused_data_rejected():
    plc = MockPlc()
    assert plc.command(20, 1, 0, a=1)["result"] == 9
    assert plc.command(20, 1, 0, staging=[1])["result"] == 9
    plc.handshake = False
    assert plc.command(9)["result"] == 1
    assert plc.snapshot()["signature"] != 0


def test_config_epoch_wraps_on_parameter_commit():
    plc = MockPlc()
    plc.config_epoch = 65535
    assert plc.command(31, 1, 0, a=0, b=1000, c=1000)["result"] == 0
    assert plc.config_epoch == 0


def test_p0_standby_slot_is_never_released():
    plc = MockPlc()
    assert plc.command(50, 3, 0, a=4, b=plc.config_epoch,
                       staging=pair(0) + pair(1000) + [0x40])["result"] == 9
    assert plc.snapshot()["points"][0]["owner"] == 0
