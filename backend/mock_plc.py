"""Explicit XJV1 simulation, not PLC acceptance or physical safety evidence.

Only tick() advances time. Drives use constant speed; real drive ramps, physical
sensors, and a production flow are deliberately outside this offline model.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import threading

from .xj_protocol import (AXES, CYLINDERS, POINT_FREE, POINTS, SIGNATURE, describe_alarm,
                          point_flags_valid, point_owner, rejection_message)

AXIS_FIELDS = ("positive_limit", "negative_limit", "manual_speed", "auto_speed",
               "acceleration", "deceleration", "estop_deceleration", "flags")
CYLINDER_FIELDS = ("wiring_flags", "move_y", "home_y", "move_x", "home_x",
                   "delay_ms", "timeout_ms", "home_delay_ms")
AXIS_PERMITS = (20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 50)
STOPS = {9, 10, 26, 42}
SUPPORTED = {1, 2, 3, 4, 9, 10, 11, *range(20, 32), 40, 41, 42, 50, 52, 53}


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _dword(words, offset, signed=False):
    value = (words[offset] << 16) | words[offset + 1]
    return value - 2**32 if signed and value >= 2**31 else value


class MockPlc:
    def __init__(self, persistence_path=None):
        self.lock = threading.RLock()
        self.persistence_path = Path(persistence_path) if persistence_path is not None else None
        self.bound_axes = 0b111
        self.bound_cylinders = (1 << 12) - 1
        self.axes = []
        for index in range(AXES):
            self.axes.append({
                "index": index, "bound": index < 3,
                "online": index < 3, "enabled": False, "running": False, "homed": False,
                "alarm": False, "alarm_code": 0, "drive_error": 0, "limit": False,
                "limits": 0, "static": index < 3, "jog": 0, "jog_positive": False,
                "jog_negative": False, "position": 0.0, "velocity": 0.0, "target": 0.0,
                "permit": 0, "reason": 6 if index < 3 else 4, "motion_seq": 0, "motion_result": 0,
                "config": dict(zip(AXIS_FIELDS, (1000.0, -1000.0, 40.0, 60.0, 100.0, 100.0, 200.0, 1))),
            })
        self.cylinders = []
        for index in range(CYLINDERS):
            self.cylinders.append({
                "index": index, "bound": index < 12,
                "online": index < 12, "move": False, "home": index < 12,
                "moving": False, "alarm": False, "alarm_code": 0, "masked": False,
                "permit": 0, "reason": 0 if index < 12 else 4,
                "config": dict(zip(CYLINDER_FIELDS, (1, index * 2, index * 2 + 1,
                                   index * 2, index * 2 + 1, 200, 3000, 0))),
            })
        # Shared point pool: slots 0..15 pre-own to their like-numbered axis (P0),
        # the rest are free (owner None) until claimed by teach or code 50.
        self.points = [{"index": slot, "owner": slot if slot < 16 else None,
                        "position": 0.0, "speed": 60.0,
                        "enabled": False, "taught": False}
                       for slot in range(POINTS)]
        self.connected = self.handshake = self.online = self.manual = True
        self._previous_manual = True
        self.estop = self.software_estop = False
        self.configured = self.running = self.resetting = self.paused = False
        self.flow_ready = True
        self.reset_required = True
        self.signature = SIGNATURE
        self.features = 0
        self.heartbeat = self.ack_seq = self.ack_result = self.ack_object = self.ack_epoch = 0
        self.last_rejection = self.config_epoch = self.snapshot_epoch = 0
        self.binding_epoch = 1
        self.uptime = 0.0
        self.alarms = []
        self.alarm_count = 0
        self.persistence_error = None
        self._alarm_objects = set()
        self._clock = 0.0
        self._jog = None
        self._motions = {}
        self._cylinder_motions = {}
        self._outputs = [False] * 32
        # None selects the deterministic virtual plant; bool injects raw electrical input.
        self._sensor_overrides = {}
        self._sensor_raw = {(i, side): side == "home" for i in range(CYLINDERS)
                            for side in ("move", "home")}
        self._confirmed_ms = {(i, side): 0.0 for i in range(CYLINDERS)
                              for side in ("move", "home")}
        self._time_done = {(i, side): False for i in range(CYLINDERS)
                           for side in ("move", "home")}
        self._last_ack = None
        self._load()

    def _bound(self, kind, index):
        if kind == 3:
            owner = self.points[index]["owner"]
            return owner is not None and bool(self.bound_axes & (1 << owner))
        return bool((self.bound_cylinders if kind == 2 else self.bound_axes) & (1 << index))

    def _object_error(self, code, kind, index):
        if not _integer(kind, 0, 3) or not _integer(index, 0, 255):
            return 15
        if index >= (1, AXES, CYLINDERS, POINTS)[kind]:
            return 15
        allowed = ({0} if code < 20 or code in (52, 53) else
                   {1} if code < 40 else {2} if code < 50 else {1, 2, 3})
        if kind not in allowed:
            return 15
        if kind and not self._bound(kind, index):
            if kind == 3 and self.points[index]["owner"] is None and code == 50:
                return 0
            return 4
        return 0

    def _owner(self, kind, index):
        if kind == 3:
            return self.axes[self.points[index]["owner"]]
        return self.cylinders[index] if kind == 2 else self.axes[index]

    def _target(self, kind, index):
        if kind == 3:
            return self.points[index]
        return self._owner(kind, index)

    def _permission(self, code, kind=0, index=0):
        """Shared command and published-permit decision; data validation is separate."""
        if not self.handshake or self.signature != SIGNATURE:
            return 1
        if code in STOPS:
            return 0
        if not self.online or not self.connected:
            return 2
        if code == 53:
            return 14
        if code == 11:
            return 3 if self.estop else 0
        if self.estop or self.software_estop:
            return 3
        if kind == 3 and self.points[index]["owner"] is None:
            if code != 50:
                return 4
            if not self.manual:
                return 7
            return 0
        if code in (2, 3, 4):
            if not self.configured or self.reset_required:
                return 11
            if code == 2:
                return 8 if self.running or self.paused else 0
            if code == 3:
                return 0 if self.running else 8
            return 0 if self.paused else 8
        if kind == 0:
            if code == 52:
                if self.running:
                    return 8
                if not self.manual:
                    return 7
                if any(a["running"] for a in self.axes) or any(c["moving"] for c in self.cylinders):
                    return 10
            return 0
        obj = self._owner(kind, index)
        if not self._bound(kind, index):
            return 4
        if kind == 2:
            if self.resetting:
                return 8
            if self.paused or not self.manual:
                return 7
            if code not in (40, 41, 50):
                return 14
            if obj["moving"]:
                return 10
            if code == 50:
                return 0
            cfg = obj["config"]
            if cfg["move_y"] == 65535 or cfg["wiring_flags"] & 3 in (1, 3) and cfg["home_y"] == 65535:
                return 14
            if not obj["online"]:
                return 5
            if obj["alarm"]:
                return 17
            if self.reset_required:
                return 11
            if not self.configured:
                return 14
            return self._cylinder_config_valid(cfg)
        if not obj["online"]:
            return 5
        if obj["alarm"] and code not in (21, 23):
            return 17
        if (self.running or self.paused) and code != 21:
            return 8
        if not self.manual and code != 21:
            return 7
        if kind != 2 and code in (22, 24, 25, 27, 28, 29, 30) and not obj["enabled"]:
            return 6
        if (obj.get("running") or obj.get("moving")) and code != 21:
            return 10
        if code in (24, 25):
            if self._jog is not None:
                return 10
            if self._direction_blocked(obj, 1 if code == 24 else -1):
                return 17
        if code == 29 and not any(p["owner"] == obj["index"] and p["enabled"] and p["taught"]
                                  for p in self.points):
            return 18
        return 0

    def _direction_blocked(self, axis, direction):
        if axis["limits"] & (1 if direction > 0 else 2):
            return True
        cfg = axis["config"]
        return bool(cfg["flags"] & 1 and
                    (axis["position"] >= cfg["positive_limit"] if direction > 0 else
                     axis["position"] <= cfg["negative_limit"]))

    @staticmethod
    def _position_valid(position, config):
        return (math.isfinite(position) and -2147483.648 <= position <= 2147483.647 and
                (not config["flags"] & 1 or config["negative_limit"] <= position <= config["positive_limit"]))

    @staticmethod
    def _axis_config_valid(config):
        return (_integer(config["flags"], 0, 1) and
                all(type(config[key]) in (int, float) for key in AXIS_FIELDS[:7]) and
                -2147483.648 <= config["negative_limit"] < config["positive_limit"] <= 2147483.647 and
                all(0.001 <= config[key] <= 2147483.647 for key in AXIS_FIELDS[2:7]))

    def _cylinder_config_valid(self, config):
        if any(not _integer(config[key], 0, 65535) for key in CYLINDER_FIELDS):
            return 9
        if config["wiring_flags"] & ~15:
            return 9
        mode = config["wiring_flags"] & 3
        if config["move_y"] not in (*range(128), 65535):
            return 9
        if (mode in (0, 2) and config["home_y"] != 65535 or
                mode in (1, 3) and config["home_y"] not in (*range(128), 65535)):
            return 9
        for sensor, delay in (("move_x", "delay_ms"), ("home_x", "home_delay_ms")):
            if config[sensor] not in (*range(128), 65535):
                return 9
            if not (0 <= config[delay] < config["timeout_ms"] <= 65535):
                return 9
            if config[sensor] == 65535 and not config[delay]:
                return 9
        return 0

    def _finish(self, result, object_word, sequence):
        self.ack_seq, self.ack_result, self.ack_object = sequence, result, object_word
        self.ack_epoch = (self.ack_epoch + 1) & 65535
        if result:
            self.last_rejection = result
        self.snapshot_epoch = (self.snapshot_epoch + 2) & 65535
        self._last_ack = {"result": result, "message": rejection_message(result),
                          "object": object_word, "ack_epoch": self.ack_epoch, "seq": sequence}
        return dict(self._last_ack)

    def command(self, code, object_type=0, object_index=0, a=0, b=0, c=0,
                staging=(), sequence=None):
        with self.lock:
            if sequence is None:
                sequence = self.ack_seq % 65535 + 1
            object_word = ((object_type << 8) | object_index
                           if type(object_type) is int and type(object_index) is int else 0)
            if not _integer(sequence, 1, 65535):
                return self._finish(9, object_word, self.ack_seq)
            if sequence == self.ack_seq and self._last_ack is not None:
                return dict(self._last_ack)
            if not _integer(code, 0, 65535) or code not in SUPPORTED:
                return self._finish(14, object_word, sequence)
            error = self._object_error(code, object_type, object_index)
            if error:
                return self._finish(error, object_word, sequence)
            if not self.handshake or self.signature != SIGNATURE:
                return self._finish(1, object_word, sequence)
            if code == 53:
                return self._finish(14, object_word, sequence)
            try:
                words = list(staging)
            except TypeError:
                return self._finish(9, object_word, sequence)
            if len(words) > 16 or any(not _integer(w, 0, 65535) for w in words):
                return self._finish(9, object_word, sequence)
            words += [0] * (16 - len(words))
            if not all(type(value) is int for value in (a, b, c)):
                return self._finish(9, object_word, sequence)
            if code not in (27, 28, 29, 31, 50, 52) and (a or b or c):
                return self._finish(9, object_word, sequence)
            if code != 50 and any(words):
                return self._finish(9, object_word, sequence)
            if code in (27, 28) and (not _integer(a, -2**31, 2**31 - 1) or
                                    not _integer(b, 1, 2**31 - 1) or c):
                return self._finish(9, object_word, sequence)
            if code == 29 and (not _integer(a, 0, POINTS - 1) or b or c):
                return self._finish(9, object_word, sequence)
            if code == 31 and (not _integer(a, 0, POINTS - 1) or
                               not _integer(b, -2**31, 2**31 - 1) or not _integer(c, 1, 2**31 - 1)):
                return self._finish(9, object_word, sequence)
            if code in (50, 52):
                epoch = b if code == 50 else a
                if not _integer(epoch, 0, 65535) or c or (code != 50 and b):
                    return self._finish(9, object_word, sequence)
                if epoch != self.config_epoch:
                    return self._finish(16, object_word, sequence)
            error = self._permission(code, object_type, object_index)
            if error:
                return self._finish(error, object_word, sequence)
            saved = None
            if code in (31, 50, 52):
                saved = (copy.deepcopy(self.axes), copy.deepcopy(self.cylinders),
                         copy.deepcopy(self.points), self.config_epoch,
                         self.configured, self.reset_required)
            result = self._execute(code, object_type, object_index, a, b, c, words, sequence)
            if result == 0 and saved is not None:
                try:
                    self._save()
                except (OSError, ValueError) as exc:
                    (self.axes, self.cylinders, self.points, self.config_epoch,
                     self.configured, self.reset_required) = saved
                    self.persistence_error = str(exc)
                    result = 19
            self._refresh_alarms()
            return self._finish(result, object_word, sequence)

    def _changed(self, invalidate=True):
        self.config_epoch = (self.config_epoch + 1) & 65535
        if invalidate:
            self.configured = False
            self.reset_required = True

    def _stop_axis(self, index, result=4):
        self.axes[index].update(jog=0, running=False, velocity=0.0, static=True,
                                jog_positive=False, jog_negative=False, motion_result=result)
        self._motions.pop(index, None)
        if self._jog is not None and self._jog["index"] == index:
            self._jog = None

    def set_cylinder_sensor(self, index, side, raw):
        """Inject a raw sensor level; None restores the virtual 300 ms travel model."""
        if not _integer(index, 0, CYLINDERS - 1) or side not in ("move", "home"):
            raise ValueError("Invalid cylinder sensor")
        if raw is not None and type(raw) is not bool:
            raise ValueError("raw must be bool or None")
        with self.lock:
            if raw is None:
                self._sensor_overrides.pop((index, side), None)
            else:
                self._sensor_overrides[index, side] = raw
                self._sensor_raw[index, side] = raw
                self._update_cylinder_confirmation(index, side, 0)

    def _update_cylinder_confirmation(self, index, side, milliseconds):
        cylinder = self.cylinders[index]
        cfg = cylinder["config"]
        if cfg[side + "_x"] == 65535:
            cylinder[side] = self._time_done[index, side]
            return
        active = self._sensor_raw[index, side] ^ bool(cfg["wiring_flags"] & (4 if side == "move" else 8))
        self._confirmed_ms[index, side] = (round(self._confirmed_ms[index, side] + milliseconds, 9)
                                           if active else 0)
        delay = cfg["delay_ms" if side == "move" else "home_delay_ms"]
        cylinder[side] = active and self._confirmed_ms[index, side] >= delay

    def _stop_cylinder(self, index, hold_outputs=False):
        cylinder = self.cylinders[index]
        cylinder["moving"] = False
        self._cylinder_motions.pop(index, None)
        for side in ("move", "home"):
            self._time_done[index, side] = False
            if cylinder["config"][side + "_x"] == 65535:
                cylinder[side] = False
        if hold_outputs and cylinder["config"]["wiring_flags"] & 3 == 3:
            output = cylinder["config"]["home_y"]
            if 0 <= output < len(self._outputs):
                self._outputs[output] = False
        if not hold_outputs:
            for key in ("move_y", "home_y"):
                output = cylinder["config"][key]
                if 0 <= output < len(self._outputs):
                    self._outputs[output] = False

    def _stop_all(self):
        for index in range(AXES):
            if self._bound(1, index):
                self._stop_axis(index)
        for index in range(CYLINDERS):
            if self._bound(2, index):
                self._stop_cylinder(index)
        self.running = False

    def _start_motion(self, index, target, speed, sequence, homing=False):
        axis = self.axes[index]
        if not self._position_valid(target, axis["config"]):
            return 9
        direction = 1 if target > axis["position"] else -1
        if target != axis["position"] and self._direction_blocked(axis, direction):
            return 17
        axis.update(target=target, running=True, static=False, motion_seq=sequence,
                    motion_result=1, velocity=direction * speed if target != axis["position"] else 0)
        self._motions[index] = {"target": target, "speed": speed, "homing": homing,
                                "config": copy.deepcopy(axis["config"])}
        if homing:
            axis["homed"] = False
        return 0

    def _execute(self, code, kind, index, a, b, c, words, sequence):
        if code in (9, 10):
            self._stop_all()
            self.paused = False
            if code == 10:
                self.software_estop = True
            return 0
        if code == 11:
            self.software_estop = False
            return 0
        if code == 1:
            self._stop_all()
            self.paused = False
            for objects, object_kind in ((self.axes, 1),):
                for obj in objects:
                    if self._bound(object_kind, obj["index"]):
                        obj.update(alarm=False, alarm_code=0)
            self.reset_required = False
            return 0
        if code == 2:
            self.running = True
            self.paused = False
            return 0
        if code == 3:
            for axis_index in range(AXES):
                if self._bound(1, axis_index):
                    self._stop_axis(axis_index)
            # Offline policy: pause preserves clamps, but cancels request completion.
            for cylinder_index in range(CYLINDERS):
                self._stop_cylinder(cylinder_index, hold_outputs=True)
            self.running = False
            self.paused = True
            return 0
        if code == 4:
            self.running = True
            self.paused = False
            return 0
        if code == 52:
            result = self._confirmation_error()
            if result:
                return result
            self.configured = self.reset_required = True
            self._changed(invalidate=False)
            return 0
        if code == 50:
            return self._parameters(kind, index, a, words)
        if kind == 2:
            cylinder = self.cylinders[index]
            if code == 42:
                self._stop_cylinder(index)
                if (cylinder["online"] and not self.estop and not self.software_estop
                        and not self._cylinder_config_valid(cylinder["config"])):
                    cylinder.update(alarm=False, alarm_code=0)
            else:
                cfg = cylinder["config"]
                if (self._cylinder_config_valid(cfg) or cfg["move_y"] == 65535 or
                        cfg["wiring_flags"] & 3 in (1, 3) and cfg["home_y"] == 65535):
                    return 9
                self._stop_cylinder(index)
                cylinder["moving"] = True
                self._cylinder_motions[index] = {"move": code == 40, "elapsed": 0.0}
                for side in ("move", "home"):
                    self._confirmed_ms[index, side] = 0
                    if (index, side) not in self._sensor_overrides:
                        self._sensor_raw[index, side] = bool(cfg["wiring_flags"] & (4 if side == "move" else 8))
                    self._update_cylinder_confirmation(index, side, 0)
                for key, active in (("move_y", code == 40),
                                    ("home_y", code == 41 and cfg["wiring_flags"] & 3 in (1, 3))):
                    output = cfg[key]
                    if 0 <= output < len(self._outputs):
                        self._outputs[output] = active
            return 0
        axis = self.axes[index]
        if code == 20:
            axis["enabled"] = True
        elif code == 21:
            self._stop_axis(index)
            axis["enabled"] = False
        elif code == 22:
            return self._start_motion(index, 0.0, axis["config"]["manual_speed"], sequence, homing=True)
        elif code == 23:
            axis.update(alarm=False, alarm_code=0, drive_error=0)
        elif code in (24, 25):
            direction = 1 if code == 24 else -1
            axis.update(jog=direction, running=True, static=False, jog_positive=direction > 0,
                        jog_negative=direction < 0, velocity=direction * axis["config"]["manual_speed"],
                        motion_seq=sequence, motion_result=1)
            self._jog = {"index": index, "object": 0x100 | index, "seq": sequence,
                         "counter": None, "expires": self._clock + 1.5}
        elif code == 26:
            self._stop_axis(index)
        elif code in (27, 28):
            target = a / 1000 if code == 27 else round(axis["position"] * 1000 + a, 9) / 1000
            return self._start_motion(index, target, b / 1000, sequence)
        elif code == 29:
            point = self.points[a]
            if point["owner"] != index or not point["enabled"] or not point["taught"]:
                return 18
            return self._start_motion(index, point["position"], point["speed"], sequence)
        elif code == 30:
            axis.update(position=0.0, target=0.0, homed=False)
        elif code == 31:
            point = self.points[a]
            if point["owner"] not in (None, index):
                return 18
            if not self._position_valid(b / 1000, axis["config"]):
                return 9
            point.update(owner=index, position=b / 1000, speed=c / 1000, taught=True)
            self._changed()
        else:
            return 14
        return 0

    def _parameters(self, kind, index, mask, words):
        if not _integer(mask, 1, 255 if kind == 1 else 7):
            return 9
        obj = self._target(kind, index)
        candidate = copy.deepcopy(obj if kind == 3 else obj["config"])
        if kind == 1:
            if words[15] or words[14] & ~1:
                return 9
            for bit, key in enumerate(AXIS_FIELDS):
                if mask & (1 << bit):
                    candidate[key] = words[14] if bit == 7 else _dword(words, bit * 2, bit < 2) / 1000
            if not self._axis_config_valid(candidate):
                return 9
        elif kind == 2:
            if any(words[8:]) or any(words[i] != candidate[key] for i, key in enumerate(CYLINDER_FIELDS[:5])):
                return 9
            for bit, key in enumerate(CYLINDER_FIELDS[5:]):
                if mask & (1 << bit):
                    candidate[key] = words[5 + bit]
            error = self._cylinder_config_valid(candidate)
            if error:
                return error
        else:
            # Only teaching sets taught; releasing to POINT_FREE is the one write that clears it.
            releasing = mask & 4 and words[4] == POINT_FREE
            if any(words[5:]) or not point_flags_valid(words[4]) or (bool(words[4] & 2) != obj["taught"] and not releasing):
                return 9
            if mask & 1:
                candidate["position"] = _dword(words, 0, True) / 1000
            if mask & 2:
                candidate["speed"] = _dword(words, 2) / 1000
            old_owner = obj["owner"]
            if mask & 4:
                new_owner = point_owner(words[4])
                candidate["enabled"] = bool(words[4] & 1)
                if old_owner is None:
                    if new_owner is None or not self._bound(1, new_owner):
                        return 4 if new_owner is not None else 9
                    candidate["owner"] = new_owner
                elif new_owner is None:
                    if words[4] != POINT_FREE or index == old_owner or obj["enabled"]:  # P0 stays owned
                        return 9
                    candidate.update(owner=None, taught=False, enabled=False)
                elif new_owner != old_owner:
                    return 9
            elif old_owner is None:
                return 9
            if candidate["owner"] is None:
                if candidate["enabled"] or candidate["taught"]:
                    return 9
            else:
                if (candidate["enabled"] and not candidate["taught"] or
                        not 0.001 <= candidate["speed"] <= 2147483.647 or
                        not self._position_valid(candidate["position"],
                                                 self.axes[candidate["owner"]]["config"])):
                    return 9
        if kind == 3:
            obj.update(candidate)
        else:
            obj["config"] = candidate
        self._changed()
        return 0

    def _confirmation_error(self):
        for index, axis in enumerate(self.axes):
            if not self._bound(1, index):
                continue
            if not axis["online"]:
                return 5
            if axis["alarm"]:
                return 17
            if not axis["config"]["flags"] & 1 or not self._axis_config_valid(axis["config"]):
                return 9
            point = self.points[index]
            if point["owner"] != index or not point["enabled"] or not point["taught"]:
                return 18
            if not self._position_valid(point["position"], axis["config"]):
                return 9
        for index, cylinder in enumerate(self.cylinders):
            if not self._bound(2, index):
                continue
            if not cylinder["online"]:
                return 5
            if cylinder["alarm"]:
                return 17
            cfg = cylinder["config"]
            if (self._cylinder_config_valid(cfg) or cfg["move_y"] == 65535 or
                    cfg["wiring_flags"] & 3 in (1, 3) and cfg["home_y"] == 65535):
                return 9
        return 0

    def renew_jog(self, object_word, seq, counter):
        with self.lock:
            jog = self._jog
            if (jog is None or not _integer(counter, 0, 65535) or
                    object_word != jog["object"] or seq != jog["seq"] or
                    counter == jog["counter"] or self._clock >= jog["expires"] or
                    not self.online or not self.connected or self.estop or self.software_estop):
                return False
            jog.update(counter=counter, expires=self._clock + 1.5)
            return True

    def tick(self, elapsed=0.1):
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("elapsed must be a finite nonnegative number of seconds")
        with self.lock:
            previous = self._clock
            self._clock = round(self._clock + elapsed, 9)
            self.uptime = self._clock
            self.heartbeat = int((self._clock + 1e-9) / 0.2) & 65535
            if self.estop or self.software_estop:
                self._stop_all()
            if self.manual != self._previous_manual:
                for index in range(CYLINDERS):
                    self._stop_cylinder(index, hold_outputs=True)
                self._previous_manual = self.manual
            for index, axis in enumerate(self.axes):
                if not axis["running"]:
                    continue
                if not self._bound(1, index) or not axis["online"] or not axis["enabled"] or axis["alarm"]:
                    self._stop_axis(index)
                    continue
                if axis["jog"]:
                    if not self.online or not self.connected or self._jog is None:
                        self._stop_axis(index)
                        continue
                    dt = max(0.0, min(self._clock, self._jog["expires"]) - previous)
                    cfg = axis["config"]
                    position = axis["position"] + axis["velocity"] * dt
                    low, high = ((cfg["negative_limit"], cfg["positive_limit"]) if cfg["flags"] & 1
                                 else (-2147483.648, 2147483.647))
                    if self._direction_blocked(axis, axis["jog"]):
                        self._stop_axis(index)
                        continue
                    axis["position"] = max(low, min(high, position))
                    if position <= low or position >= high or self._clock >= self._jog["expires"]:
                        self._stop_axis(index)
                elif index in self._motions:
                    motion = self._motions[index]
                    delta = motion["target"] - axis["position"]
                    direction = 1 if delta > 0 else -1
                    if delta and self._direction_blocked(axis, direction):
                        self._stop_axis(index)
                        continue
                    distance = min(abs(delta), motion["speed"] * elapsed)
                    axis["position"] += direction * distance
                    if distance >= abs(delta):
                        axis["position"] = motion["target"]
                        if motion["homing"]:
                            axis["homed"] = True
                        self._stop_axis(index, result=2)
            for index, cylinder in enumerate(self.cylinders):
                motion = self._cylinder_motions.get(index)
                cfg = cylinder["config"]
                if not self._bound(2, index) or not cylinder["online"] or cylinder["alarm"]:
                    self._stop_cylinder(index)
                    continue
                if not self.connected or not self.online or not self.handshake:
                    self._stop_cylinder(index, hold_outputs=True)
                    continue
                old = motion["elapsed"] if motion else 0
                end = round(old + elapsed, 9)
                target = ("move" if motion["move"] else "home") if motion else None
                completion = math.inf
                for side in ("move", "home"):
                    delay = cfg["delay_ms" if side == "move" else "home_delay_ms"] / 1000
                    duration = elapsed
                    if cfg[side + "_x"] == 65535:
                        if side == target:
                            completion = delay
                        self._update_cylinder_confirmation(index, side, 0)
                        continue
                    invert = bool(cfg["wiring_flags"] & (4 if side == "move" else 8))
                    if motion and (index, side) not in self._sensor_overrides:
                        active = side == target and end >= 0.3
                        self._sensor_raw[index, side] = active ^ invert
                        duration = max(0, end - max(old, 0.3)) if active else 0
                        if side == target:
                            completion = 0.3 + delay
                    elif side == target and self._sensor_raw[index, side] ^ invert:
                        completion = old + max(0, delay - self._confirmed_ms[index, side] / 1000)
                    self._update_cylinder_confirmation(index, side, duration * 1000)
                if motion:
                    motion["elapsed"] = end
                    timeout = cfg["timeout_ms"] / 1000
                    if end >= timeout and timeout <= completion:
                        cylinder.update(alarm=True, alarm_code=2140)
                        self._stop_cylinder(index)
                    elif end >= completion:
                        if cfg[target + "_x"] == 65535:
                            self._time_done[index, target] = True
                            cylinder[target] = True
                        cylinder["moving"] = False
                        self._cylinder_motions.pop(index)
                        if (target == "home" and cfg["wiring_flags"] & 3 == 3
                                and 0 <= cfg["home_y"] < len(self._outputs)):
                            self._outputs[cfg["home_y"]] = False
            self._refresh_alarms()
            if elapsed:
                self.snapshot_epoch = (self.snapshot_epoch + 2) & 65535

    def _refresh_alarms(self):
        alarms = []
        for kind, objects in ((1, self.axes), (2, self.cylinders)):
            for index, obj in enumerate(objects):
                if self._bound(kind, index) and obj["alarm"]:
                    alarms.append(describe_alarm(kind, {**obj, "bound": True}))
        active = {alarm["object"] for alarm in alarms}
        self.alarm_count = min(65535, self.alarm_count + len(active - self._alarm_objects))
        self._alarm_objects = active
        self.alarms = alarms

    def snapshot(self):
        with self.lock:
            axes = copy.deepcopy(self.axes)
            cylinders = copy.deepcopy(self.cylinders)
            for index, axis in enumerate(axes):
                bound = self._bound(1, index)
                axis["bound"], axis["online"] = bound, bound and axis["online"]
                axis["static"] = bound and not axis["running"]
                cfg = axis["config"]
                axis["limits"] = axis["limits"] & 3
                if cfg["flags"] & 1:
                    axis["limits"] |= 4 if axis["position"] >= cfg["positive_limit"] else 0
                    axis["limits"] |= 8 if axis["position"] <= cfg["negative_limit"] else 0
                axis["limit"] = bound and bool(axis["limits"])
                axis["permit"] = sum(1 << bit for bit, code in enumerate(AXIS_PERMITS)
                                     if bound and not self._permission(code, 1, index))
                axis["reason"] = self._permission(27, 1, index) if bound else 4
                axis["points"] = [copy.deepcopy(point) for point in self.points
                                  if point["owner"] == index]
            for index, cylinder in enumerate(cylinders):
                bound = self._bound(2, index)
                cylinder["bound"], cylinder["online"] = bound, bound and cylinder["online"]
                cylinder["masked"] = False
                for side in ("move", "home"):
                    if cylinder["config"][side + "_x"] == 65535:
                        cylinder[side] = bound and self._time_done[index, side]
                cylinder["permit"] = sum(1 << bit for bit, code in enumerate((40, 41, 50))
                                         if bound and not self._permission(code, 2, index))
                cylinder["reason"] = self._permission(40, 2, index) if bound else 4
            global_permit = sum(1 << bit for bit, permitted in enumerate((
                any(a["permit"] & 1 for a in axes), any(a["permit"] & 48 for a in axes),
                any(a["permit"] & 448 for a in axes), any(c["permit"] & 3 for c in cylinders),
                self._permission(1) == 0, self._permission(2) == 0,
                self._permission(3) == 0, self._permission(4) == 0,
                self.software_estop and self._permission(11) == 0,
                self._permission(52) == 0 and self._confirmation_error() == 0,
            )) if permitted)
            inputs = [False] * 32
            for cylinder in cylinders:
                if cylinder["bound"]:
                    for side in ("move", "home"):
                        index = cylinder["config"][side + "_x"]
                        if 0 <= index < len(inputs):
                            inputs[index] = self._sensor_raw[cylinder["index"], side]
            return {
                "mode": "mock", "simulation": True, "connected": self.connected,
                "handshake": self.handshake, "signature": SIGNATURE, "heartbeat": self.heartbeat,
                "ack_seq": self.ack_seq, "ack_result": self.ack_result, "ack_object": self.ack_object,
                "ack_epoch": self.ack_epoch, "online": self.online, "manual": self.manual,
                "running": self.running, "resetting": self.resetting, "paused": self.paused,
                "estop": self.estop or self.software_estop, "software_estop": self.software_estop,
                "alarm": bool(self.alarms), "configured": self.configured, "flow_ready": True,
                "reset_required": self.reset_required, "global_permit": global_permit,
                "global_reason": 0 if global_permit else self._permission(1),
                "first_alarm": self.alarms[0]["code"] if self.alarms else 0,
                "first_alarm_object": self.alarms[0]["object"] if self.alarms else 0,
                "alarm_count": self.alarm_count, "last_rejection": self.last_rejection, "step": 0,
                "uptime": int(self.uptime + 1e-9) & 0xFFFFFFFF,
                "binding_epoch": self.binding_epoch, "config_epoch": self.config_epoch,
                "features": self.features, "snapshot_epoch": self.snapshot_epoch,
                "axes": axes, "cylinders": cylinders, "points": copy.deepcopy(self.points),
                "alarms": copy.deepcopy(self.alarms),
                "io": {"x": inputs, "y": list(self._outputs)}, "persistence_error": self.persistence_error,
            }

    def _save(self):
        if self.persistence_path is None:
            return
        data = {"signature": SIGNATURE, "simulation_only": True,
                "axes": [{"config": axis["config"]} for axis in self.axes],
                "cylinders": [{"config": cylinder["config"]} for cylinder in self.cylinders],
                "points": self.points}
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.persistence_path.with_name(self.persistence_path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=True, allow_nan=False), encoding="utf-8")
            temporary.replace(self.persistence_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        self.persistence_error = None

    def _load(self):
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        try:
            data = json.loads(self.persistence_path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("signature") not in (SIGNATURE, 0x584A5632) or
                    data.get("simulation_only") is not True):
                raise ValueError("Not an XJV1 simulation persistence file")
            axes, cylinders = copy.deepcopy(self.axes), copy.deepcopy(self.cylinders)
            if (len(data["axes"]) != AXES or len(data["cylinders"]) != CYLINDERS
                    or len(data.get("points", ())) != POINTS):
                raise ValueError("Invalid simulation capacities")
            for axis, stored in zip(axes, data["axes"]):
                if set(stored["config"]) != set(AXIS_FIELDS) or not self._axis_config_valid(stored["config"]):
                    raise ValueError("Invalid persisted axis configuration")
                axis["config"] = stored["config"]
            # Names were dropped from the simulator in protocol 1.2; ignore old keys.
            points = [{key: value for key, value in point.items() if key != "name"} for point in data["points"]]
            for slot, point in enumerate(points):
                if (set(point) != {"index", "owner", "position", "speed", "enabled", "taught"} or
                        point["index"] != slot or point["owner"] is not None and
                        not 0 <= point["owner"] < AXES or point["owner"] is None and
                        (point["enabled"] or point["taught"]) or point["enabled"] and not point["taught"] or
                        not 0.001 <= point["speed"] <= 2147483.647 or
                        point["owner"] is not None and not self._position_valid(
                            point["position"], dict(axes[point["owner"]]["config"], flags=0))):
                    raise ValueError(f"模拟持久化文件中点位 {slot} 无效")
            for cylinder, stored in zip(cylinders, data["cylinders"]):
                cfg = dict(stored["config"])
                if data["signature"] == 0x584A5632:
                    if set(cfg) != (set(CYLINDER_FIELDS) - {"home_delay_ms"}) | {"flags"} or cfg["flags"] != 0:
                        raise ValueError("Invalid legacy cylinder configuration")
                    cfg.pop("flags")
                    cfg["home_delay_ms"] = cfg["delay_ms"]
                if (set(cfg) != set(CYLINDER_FIELDS) or self._cylinder_config_valid(cfg) or
                        any(cfg[key] != cylinder["config"][key] for key in CYLINDER_FIELDS[:5])):
                    raise ValueError("Invalid persisted cylinder configuration")
                cylinder["config"] = cfg
            self.axes, self.cylinders = axes, cylinders
            self.points = points
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            self.persistence_error = str(exc)

    def close(self):
        with self.lock:
            self._stop_all()
            self._save()
