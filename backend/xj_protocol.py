"""XJV1 wire codec. Register addresses are loaded from the reviewed JSON map."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "docs/protocol-v1.json").read_text(encoding="utf-8"))
SIGNATURE = SPEC["signature"]
AXES = SPEC["capacities"]["axes"]
CYLINDERS = SPEC["capacities"]["cylinders"]
POINTS = SPEC["capacities"]["points"]
REJECTIONS = {item["code"]: item for item in SPEC["rejections"]}
WINDOWS = {item["id"]: item for item in SPEC["windows"]}
COMMAND_BASE = WINDOWS["command"]["base"]
STATUS_BASE = WINDOWS["status"]["base"]
STATUS_OFFSET = {field["id"]: field["offset"] for field in WINDOWS["status"]["fields"]}
AXIS_LIVE_STRIDE = WINDOWS["axis_live"]["stride"]
POINT_FLAGS = SPEC["point_flags"]
POINT_FREE = POINT_FLAGS["free"]
ALARMS = {item["code"]: item for item in SPEC["alarms"]}
COMMANDS = {item["code"]: item for item in SPEC["commands"]}
OBJECT_KINDS = {0: "系统", 1: "轴", 2: "气缸", 3: "点位"}


def u16(value: int) -> int:
    return int(value) & 0xFFFF


def s16(value: int) -> int:
    value = u16(value)
    return value - 0x10000 if value & 0x8000 else value


def dword(words: Iterable[int], signed: bool = False) -> int:
    values = list(words)
    value = 0
    for word in values:
        value = (value << 16) | u16(word)
    if signed and len(values) == 2 and value & 0x80000000:
        return value - 0x100000000
    return value


def split_dword(value: int) -> list[int]:
    value = int(value) & 0xFFFFFFFF
    return [(value >> 16) & 0xFFFF, value & 0xFFFF]


def point_owner(flags: int) -> int | None:
    """Owner axis of a pool slot, or None for the free-slot encoding."""
    flags = u16(flags)
    if flags == POINT_FREE:
        return None
    return (flags >> POINT_FLAGS["owner_shift"]) & POINT_FLAGS["owner_mask"]


def point_flags(owner: int | None, enabled: bool = False, taught: bool = False) -> int:
    if owner is None:
        return POINT_FREE
    return (owner << POINT_FLAGS["owner_shift"]) | (int(taught) << 1) | int(enabled)


def point_flags_valid(flags: int) -> bool:
    """Free is exactly POINT_FREE; owned slots never set the free bit or enabled-without-taught."""
    flags = u16(flags)
    if flags == POINT_FREE:
        return True
    return not flags & ~POINT_FLAGS["valid_mask"] and not flags & POINT_FREE and flags & 3 != 1


@dataclass(frozen=True)
class Command:
    code: int
    object_type: int = 0
    object_index: int = 0
    a: int = 0
    b: int = 0
    c: int = 0
    sequence: int = 1
    staging: tuple[int, ...] = ()

    @property
    def object_word(self) -> int:
        return (self.object_type << 8) | self.object_index


def encode_command(command: Command, heartbeat: int, signature: int = SIGNATURE) -> list[int]:
    validate_command(command)
    words = [0] * WINDOWS["command"]["stride"]
    words[0:2] = split_dword(signature)
    words[2] = u16(heartbeat)
    words[3] = u16(command.code)
    words[4] = u16(command.sequence)
    words[5] = u16(command.object_word)
    words[6:8] = split_dword(command.a)
    words[8:10] = split_dword(command.b)
    words[10:12] = split_dword(command.c)
    payload = list(command.staging)[:16]
    words[16:16 + len(payload)] = [u16(value) for value in payload]
    return words


def _window_words(registers: list[int], name: str) -> list[int]:
    window = WINDOWS[name]
    base = window["base"]
    end = base + window["stride"] * window["count"]
    return list(registers[base:end])


def decode_snapshot(data: dict) -> dict:
    status = list(data.get("status", []))
    if len(status) < WINDOWS["status"]["stride"]:
        return {"connected": False, "handshake": False, "axes": [], "cylinders": [], "alarms": []}
    signature = dword(status[0:2])
    system = u16(status[STATUS_OFFSET["system"]])
    bound_axes = u16(status[STATUS_OFFSET["axis_bound"]])
    online_axes = u16(status[STATUS_OFFSET["axis_online"]])
    cylinder_bound = STATUS_OFFSET["cylinder_bound"]
    cylinder_online = STATUS_OFFSET["cylinder_online"]
    bound_cylinders = dword(status[cylinder_bound:cylinder_bound + 4])
    online_cylinders = dword(status[cylinder_online:cylinder_online + 4])
    axis_summary = STATUS_OFFSET["axis_summary"]
    cylinder_summary = STATUS_OFFSET["cylinder_summary"]
    axes = []
    live = list(data.get("axis_live", []))
    for index in range(AXES):
        flags = u16(status[axis_summary + index])
        block = live[index * AXIS_LIVE_STRIDE:(index + 1) * AXIS_LIVE_STRIDE]
        axes.append({
            "index": index, "name": f"轴 {index}",
            "bound": bool(bound_axes & (1 << index)), "online": bool(online_axes & (1 << index)),
            "enabled": bool(flags & 1), "running": bool(flags & 2), "homed": bool(flags & 4),
            "alarm": bool(flags & 8), "limit": bool(flags & 16), "static": bool(flags & 32),
            "jog_positive": bool(flags & 64), "jog_negative": bool(flags & 128),
            "position": dword(block[0:2], True) / 1000 if len(block) >= 2 else 0,
            "velocity": dword(block[2:4], True) / 1000 if len(block) >= 4 else 0,
            "target": dword(block[4:6], True) / 1000 if len(block) >= 6 else 0,
            "permit": u16(block[6]) if len(block) > 6 else 0,
            "reason": u16(block[7]) if len(block) > 7 else 4,
            "alarm_code": u16(block[8]) if len(block) > 8 else 0,
            "drive_error": dword(block[9:11]) if len(block) > 10 else 0,
            "motion_seq": u16(block[11]) if len(block) > 11 else 0,
            "motion_result": u16(block[12]) if len(block) > 12 else 0,
            "limits": u16(block[13]) if len(block) > 13 else 0,
        })
    cylinders = []
    cyl_live = list(data.get("cylinder_live", []))
    for index in range(CYLINDERS):
        flags = u16(status[cylinder_summary + index])
        block = cyl_live[index * 3:(index + 1) * 3]
        cylinders.append({
            "index": index, "name": f"气缸 {index}",
            "bound": bool(bound_cylinders & (1 << index)), "online": bool(online_cylinders & (1 << index)),
            "move": bool(flags & 1), "home": bool(flags & 2), "moving": bool(flags & 4),
            "alarm": bool(flags & 8), "masked": False,
            "permit": u16(block[0]) if len(block) else 0, "reason": u16(block[1]) if len(block) > 1 else 4,
            "alarm_code": u16(block[2]) if len(block) > 2 else 0,
        })
    alarms = []
    for kind, items in ((1, axes), (2, cylinders)):
        for item in items:
            if item["bound"] and (item["alarm"] or item["alarm_code"]):
                alarms.append(describe_alarm(kind, item))
    return {
        "connected": signature == SIGNATURE, "handshake": signature == SIGNATURE, "signature": signature,
        "heartbeat": u16(status[2]), "ack_seq": u16(status[3]), "ack_result": u16(status[4]),
        "ack_epoch": u16(status[6]), "ack_object": u16(status[5]), "system": system, "online": bool(system & 1),
        "manual": bool(system & 2), "running": bool(system & 4), "resetting": bool(system & 8),
        "estop": bool(system & 16 or system & (1 << 9)), "alarm": bool(system & 32),
        "configured": bool(system & 64), "flow_ready": bool(system & 128),
        "reset_required": bool(system & 256),
        "paused": bool(system & 1024),
        "global_permit": u16(status[STATUS_OFFSET["global_permit"]]),
        "global_reason": u16(status[STATUS_OFFSET["global_reason"]]),
        "first_alarm": u16(status[STATUS_OFFSET["first_alarm"]]),
        "alarm_count": u16(status[STATUS_OFFSET["alarm_count"]]),
        "last_rejection": u16(status[STATUS_OFFSET["last_rejection"]]),
        "step": dword(status[STATUS_OFFSET["step"]:STATUS_OFFSET["step"] + 2]),
        "binding_epoch": u16(status[STATUS_OFFSET["binding_epoch"]]),
        "config_epoch": u16(status[STATUS_OFFSET["config_epoch"]]),
        "features": u16(status[STATUS_OFFSET["features"]]),
        "snapshot_epoch": u16(status[STATUS_OFFSET["snapshot_epoch"]]),
        "axes": axes, "cylinders": cylinders, "alarms": alarms,
    }


def describe_alarm(kind: int, item: dict) -> dict:
    """One concrete alarm record: object, code, cause, remedy and drive diagnostics."""
    detail = alarm_detail(item["alarm_code"]) if item["alarm_code"] else {
        "code": 0, "message": "对象报警位有效但未发布报警码", "action": "查看PLC诊断"}
    record = {"object": (kind << 8) | item["index"], "kind": {1: "axis", 2: "cylinder"}[kind],
              "index": item["index"], **detail}
    if kind == 1:
        if item.get("drive_error"):
            record["drive_error"] = item["drive_error"]
            record["message"] += f"；驱动错误码 0x{item['drive_error']:08X}"
        limits = item.get("limits", 0)
        if limits & 3:
            record["message"] += "；" + "、".join(text for bit, text in ((1, "正限位有效"), (2, "负限位有效")) if limits & bit)
    return record


def rejection_message(code: int) -> str:
    return REJECTIONS.get(int(code), {"message": f"未知拒绝码 {code}"})["message"]


def rejection_action(code: int) -> str:
    return REJECTIONS.get(int(code), {"action": "核对PLC固件与上位机协议版本"})["action"]


def alarm_detail(code: int) -> dict:
    item = ALARMS.get(int(code))
    if item:
        return {"code": item["code"], "message": item["message"], "action": item["action"]}
    return {"code": int(code), "message": f"未登记的报警码 {code}", "action": "查看PLC诊断并补充报警码表"}


def command_name(code: int) -> str:
    return COMMANDS.get(int(code), {"name": f"命令 {code}"})["name"]


def object_label(object_word: int, names: dict | None = None) -> str:
    """Human-readable object, e.g. '轴 2（送料轴）' or '系统'."""
    kind, index = (int(object_word) >> 8) & 0xFF, int(object_word) & 0xFF
    if kind == 0:
        return "系统"
    label = f"{OBJECT_KINDS.get(kind, f'类型{kind}')} {index}"
    key = {1: "axis", 2: "cylinder", 3: "point"}.get(kind)
    name = (names or {}).get(f"{key}:{index}") if key else None
    return f"{label}（{name}）" if name else label


def scaled(value) -> int:
    try:
        number = Decimal(str(value)) * 1000
        if not number.is_finite() or number != number.to_integral_value() or not -2**31 <= number < 2**31:
            raise ValueError("数值超出DINT范围或超过三位小数")
        return int(number)
    except InvalidOperation as exc:
        raise ValueError("无效数值") from exc


def validate_command(cmd: Command):
    allowed = {item["code"] for item in SPEC["commands"]}
    if cmd.code not in allowed:
        raise ValueError("不支持的命令")
    limits = {0: 1, 1: AXES, 2: CYLINDERS, 3: POINTS}
    if cmd.object_type not in limits or not 0 <= cmd.object_index < limits[cmd.object_type]:
        raise ValueError("对象类型或索引越界")
    expected = {1} if 20 <= cmd.code <= 31 else {2} if 40 <= cmd.code <= 42 else {1, 2, 3} if cmd.code == 50 else {0}
    if cmd.object_type not in expected:
        raise ValueError("命令与对象类型不匹配")
    if not 1 <= cmd.sequence <= 65535:
        raise ValueError("SEQ必须为1..65535")
    for name, value in (("a", cmd.a), ("b", cmd.b), ("c", cmd.c)):
        signed = (cmd.code in (27, 28) and name == "a") or (cmd.code == 31 and name == "b")
        low, high = (-2**31, 2**31 - 1) if signed else (0, 2**32 - 1)
        if type(value) is not int or not low <= value <= high:
            raise ValueError("命令参数超出范围")
    if cmd.code in (27, 28) and not 1 <= cmd.b <= 2**31 - 1:
        raise ValueError("速度必须大于0")
    if cmd.code in (29, 31) and not 0 <= cmd.a < POINTS:
        raise ValueError("点位槽号必须为0..119")
    if cmd.code == 31 and not 1 <= cmd.c <= 2**31 - 1:
        raise ValueError("点位速度必须大于0")
    if len(cmd.staging) > 16 or any(type(v) is not int or not 0 <= v <= 65535 for v in cmd.staging):
        raise ValueError("提交缓冲必须为最多16个WORD")


def address(window, field=None, index=0):
    block = WINDOWS[window]
    if not 0 <= index < block["count"]:
        raise ValueError("寄存器对象越界")
    offset = 0 if field is None else next(f["offset"] for f in block["fields"] if f["id"] == field)
    return block["base"] + index * block["stride"] + offset


def record_decode(window, words):
    result = {}
    for field in WINDOWS[window]["fields"]:
        if field["type"] == "ZERO":
            continue
        offset, count = field["offset"], field["words"]
        value = dword(words[offset:offset + count], field["type"] == "DINT")
        if window in ("axis_config", "points") and field["type"] in ("DINT", "UDINT"):
            value /= 1000
        result[field["id"]] = value
    return result


def record_encode(window, values):
    words = [0] * WINDOWS[window]["stride"]
    for field in WINDOWS[window]["fields"]:
        if field["type"] == "ZERO":
            continue
        value = values[field["id"]]
        if window in ("axis_config", "points") and field["type"] in ("DINT", "UDINT"):
            value = scaled(value)
        elif type(value) is not int or not 0 <= value <= 65535:
            raise ValueError("字段必须为WORD整数")
        if field["type"] == "UDINT" and value <= 0:
            raise ValueError("速度或加减速度必须大于0")
        offset, count = field["offset"], field["words"]
        words[offset:offset + count] = split_dword(value) if count == 2 else [value]
    return words
