"""Host-owned display names (protocol 1.2): never written to the PLC.

Names are keyed by device profile + object kind + index. The PLC binding epoch is
recorded so a rebinding is flagged instead of silently relabelling new hardware.
Writes are atomic (temp file + replace) and keep the previous file as .bak.
"""
import json
from pathlib import Path
from threading import RLock

from .xj_protocol import AXES, CYLINDERS, POINTS

SCHEMA_VERSION = 2
KINDS = {"axis": AXES, "cylinder": CYLINDERS, "point": POINTS}
DEFAULT_LABELS = {"axis": "轴", "cylinder": "气缸", "point": "点位"}
MAX_NAME = 32


class NameConflict(RuntimeError):
    """The caller edited an older revision of the profile."""


def default_name(kind, index):
    return f"{DEFAULT_LABELS[kind]} {index}"


def validate_name(name):
    text = name.strip()
    if not text or len(text) > MAX_NAME:
        raise ValueError(f"名称长度必须为 1..{MAX_NAME} 个字符")
    if any(ord(ch) < 32 or 0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        raise ValueError("名称不能包含控制字符或孤立代理项")
    return text


class NameStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.lock = RLock()
        self.error = ""
        self.profiles = self._load()

    def _read(self, path):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("名称文件格式错误")
        if "profiles" not in data:
            # Flat layout from the first 1.2 draft, which only ever ran against the
            # simulator: keep those names on the simulator profile.
            return {"mock": {"names": dict(data.get("names", {})), "revision": 0, "binding_epoch": None}}
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"名称文件版本 {data.get('schema_version')} 不受支持")
        return data["profiles"]

    def _load(self):
        if self.path is None:
            return {}
        backup = self.path.with_name(self.path.name + ".bak")
        try:
            return self._read(self.path)
        except FileNotFoundError:
            if not backup.exists():
                return {}  # first run
            problem = "名称文件缺失（可能在保存中途断电）"
        except (OSError, ValueError) as exc:
            problem = f"名称文件损坏（{exc}）"
        try:
            profiles = self._read(backup)
            self.error = f"{problem}，已从备份恢复"
            return profiles
        except (OSError, ValueError):
            self.error = f"{problem}且无可用备份，当前显示默认名称"
            return {}

    def _save(self, profiles):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"schema_version": SCHEMA_VERSION, "profiles": profiles}, ensure_ascii=False, indent=2)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        # Copy (not move) the current file to .bak, so names.json exists at every
        # instant; a crash leaves either the old or the new complete file.
        if self.path.exists():
            backup = self.path.with_name(self.path.name + ".bak")
            backup_tmp = backup.with_name(backup.name + ".tmp")
            backup_tmp.write_bytes(self.path.read_bytes())
            backup_tmp.replace(backup)
        temporary.replace(self.path)

    def profile(self, profile):
        with self.lock:
            entry = self.profiles.get(profile, {})
            return {"names": dict(entry.get("names", {})), "revision": entry.get("revision", 0),
                    "binding_epoch": entry.get("binding_epoch")}

    def set(self, profile, kind, index, name=None, revision=None, binding_epoch=None):
        if kind not in KINDS or not 0 <= index < KINDS[kind]:
            raise ValueError("名称对象类型或索引越界")
        text = validate_name(name) if name is not None else None
        with self.lock:
            current = self.profile(profile)
            if revision is not None and revision != current["revision"]:
                raise NameConflict(f"名称已被其他终端修改（当前版本 {current['revision']}），请刷新后再改")
            names = current["names"]
            key = f"{kind}:{index}"
            if text is None:
                names.pop(key, None)
            else:
                names[key] = text
            entry = {"names": names, "revision": current["revision"] + 1,
                     "binding_epoch": binding_epoch if binding_epoch is not None else current["binding_epoch"]}
            profiles = {**self.profiles, profile: entry}
            self._save(profiles)
            self.profiles = profiles
            self.error = ""
            return self.profile(profile)

    def merge(self, profile, state):
        """Overlay names on a PLC state; display only, never fed back to the PLC."""
        entry = self.profile(profile)
        names = entry["names"]
        for kind, collection in (("axis", "axes"), ("cylinder", "cylinders"), ("point", "points")):
            for item in state.get(collection, []):
                item["name"] = names.get(f"{kind}:{item['index']}", default_name(kind, item["index"]))
        # Each axis also carries its own copy of its points (separate objects in the simulator).
        for axis in state.get("axes", []):
            for point in axis.get("points", []):
                point["name"] = names.get(f"point:{point['index']}", default_name("point", point["index"]))
        state["names"] = names
        state["names_revision"] = entry["revision"]
        state["names_profile"] = profile
        plc_epoch = state.get("binding_epoch")
        state["names_stale"] = bool(names) and entry["binding_epoch"] is not None and plc_epoch is not None \
            and entry["binding_epoch"] != plc_epoch
        state["names_error"] = self.error
        return state
