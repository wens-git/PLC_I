"""Shared application service for HTTP and QWebChannel transports."""
import re
import time
from pathlib import Path
from threading import RLock
from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictInt
from typing import Literal
from .comm_worker import CommWorker
from .mock_plc import MockPlc
from .name_store import MAX_NAME, NameConflict, NameStore
from .plc_transport import PlcTransport
from .xj_protocol import POINTS, POINT_FREE, SPEC, point_flags, record_encode, scaled

VERSION = "1.2.0"  # protocol 1.2


class ConnectRequest(BaseModel):
    mode: Literal["mock", "tcp"]
    host: str = Field(default="192.168.6.6", min_length=1, max_length=253)
    port: int = Field(default=SPEC["transport"]["port"], ge=1, le=65535)
    unit: int = Field(default=SPEC["transport"]["unit"], ge=1, le=247)
    # Device profile for host-owned names; defaults to host:port/unit when blank.
    profile: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_.:/-]+$")


class SessionRequest(BaseModel):
    session: str


class CommandRequest(SessionRequest):
    code: StrictInt
    object_type: StrictInt = 0
    object_index: StrictInt = 0
    a: StrictInt = 0
    b: StrictInt = 0
    c: StrictInt = 0
    staging: list[StrictInt] = Field(default_factory=list, max_length=16)


class ConfigRequest(SessionRequest):
    object_type: int = Field(ge=1, le=3)
    object_index: int = Field(ge=0, le=119)
    values: dict[str, float | int | bool]
    epoch: int = Field(ge=0, le=65535)


class NameRequest(SessionRequest):
    object_type: int = Field(ge=1, le=3)
    object_index: int = Field(ge=0, le=119)
    revision: int | None = Field(default=None, ge=0)


class NameWriteRequest(NameRequest):
    name: str = Field(min_length=1, max_length=MAX_NAME)


class PointRequest(SessionRequest):
    axis: int = Field(ge=0, le=15)
    point: int = Field(ge=0, le=119)
    position: float
    speed: float


class JogToken(SessionRequest):
    token: str = Field(min_length=1, max_length=128)


class JogStart(JogToken):
    axis: int = Field(ge=0, le=15)
    direction: Literal[-1, 1]


class Host:
    def __init__(self, persistence_path=None, names_path=None):
        self.worker = None
        self.lock = RLock()
        self.persistence_path = persistence_path
        if names_path is None and persistence_path is not None:
            names_path = Path(persistence_path).with_name("names.json")
        self.names = NameStore(names_path)
        self.profile = "mock"

    def state(self):
        with self.lock:
            if self.worker:
                return self.names.merge(self.profile, self.worker.state())
            return self.names.merge(self.profile, {
                "connected": False, "handshake": False, "mode": "offline", "session": "",
                "error": "未连接", "axes": [], "cylinders": [], "events": [], "alarms": [],
                "io": {"x": [], "y": []}, "config_epoch": 0, "global_permit": 0})

    def disconnect(self):
        with self.lock:
            if self.worker:
                self.worker.stop()
                self.worker = None

    def connect(self, request):
        with self.lock:
            self.disconnect()
            transport = MockPlc(persistence_path=self.persistence_path) if request.mode == "mock" else PlcTransport(request.host, request.port, request.unit)
            # Real devices and the simulator never share a name profile.
            self.profile = "mock" if request.mode == "mock" else (request.profile or f"{request.host}:{request.port}/{request.unit}")
            self.worker = CommWorker(transport, mode=request.mode,
                                     names=lambda profile=self.profile: self.names.profile(profile)["names"])
            self.worker.start()
        # The request returns while a real connection can be retrying in the worker.
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline and not self.state()["connected"]:
            time.sleep(0.01)
        return self.state()

    def current(self, session, stopping=False):
        with self.lock:
            if not self.worker or self.worker.session != session:
                raise HTTPException(409, "会话已变化，请重新读取状态")
            state = self.worker.state()
            if not stopping and (not state["connected"] or time.time() - state.get("updated", 0) > 1.5):
                raise HTTPException(409, "PLC状态不可用或过期")
            return self.worker


class HmiService:
    def __init__(self, persistence_path=None):
        self.host = Host(persistence_path)
        self.interaction_lock = RLock()
        self.interactive = True
        self.interaction_epoch = 0
        self.closed = False

    def state(self):
        return self.host.state()

    def meta(self):
        return {"version": VERSION, "rejections": SPEC["rejections"], "commands": SPEC["commands"]}

    def invalidate_interaction(self):
        with self.interaction_lock:
            self.interaction_epoch += 1
            self.interactive = False

    def cancel_jog(self):
        with self.host.lock:
            if self.host.worker:
                self.host.worker.end_jog()

    def suspend(self):
        self.invalidate_interaction()
        self.cancel_jog()

    def resume(self):
        with self.interaction_lock:
            if not self.closed:
                self.interactive = True

    def close(self):
        with self.interaction_lock:
            self.closed = True
            self.interactive = False
        self.host.disconnect()

    def dispatch(self, method, path, payload, interaction_epoch=None):
        if self.closed:
            raise HTTPException(409, "应用正在关闭")
        if not isinstance(payload, dict):
            raise ValueError("请求内容必须是对象")
        if method == "GET" and path == "/api/meta":
            return self.meta()
        if method == "GET" and path == "/api/state":
            return self.state()
        if method == "POST" and path == "/api/connect":
            return self.host.connect(ConnectRequest.model_validate(payload))
        if method == "POST" and path == "/api/disconnect":
            self.host.disconnect()
            return self.state()
        routes = {
            ("POST", "/api/command"): (CommandRequest, self.command),
            ("POST", "/api/config"): (ConfigRequest, self.config),
            ("POST", "/api/name"): (NameWriteRequest, self.name),
            ("DELETE", "/api/name"): (NameRequest, self.delete_name),
            ("POST", "/api/point"): (PointRequest, self.point),
            ("POST", "/api/jog/start"): (JogStart, self.jog_start),
            ("POST", "/api/jog/renew"): (JogToken, self.jog_renew),
            ("POST", "/api/jog/stop"): (JogToken, self.jog_stop),
        }
        if method == "DELETE" and re.fullmatch(r"/api/point/[0-9]+", path):
            return self.delete_point(int(path.rsplit("/", 1)[1]), SessionRequest.model_validate(payload))
        route = routes.get((method, path))
        if not route:
            raise HTTPException(404, "接口未开放")
        model, handler = route
        if path == '/api/jog/start':
            return self.jog_start(model.model_validate(payload), interaction_epoch)
        if path == '/api/jog/renew':
            return self.jog_renew(model.model_validate(payload), interaction_epoch)
        return handler(model.model_validate(payload))

    def wait(self, future):
        try:
            return future.result(timeout=12)
        except TimeoutError as exc:
            raise HTTPException(504, "命令结果未知，请查看诊断，禁止自动重试") from exc

    def command(self, body: CommandRequest):
        if body.code in (24, 25):
            raise HTTPException(422, "点动必须通过专用租约接口")
        worker = self.host.current(body.session, stopping=body.code in (9, 10, 26, 42))
        return self.wait(worker.command(**body.model_dump()))

    def config(self, body: ConfigRequest):
        worker = self.host.current(body.session)
        state = worker.state()
        kind = {1: "axis", 2: "cylinder", 3: "point"}[body.object_type]
        window = {1: "axis_config", 2: "cylinder_config", 3: "points"}[body.object_type]
        try:
            if body.object_type == 3:
                point = state["points"][body.object_index]
                current = {"position": point["position"], "speed": point["speed"],
                           "flags": point_flags(point["owner"], point["enabled"], point["taught"])}
            else:
                current = state["axes" if body.object_type == 1 else "cylinders"][body.object_index]["config"]
        except (IndexError, KeyError):
            raise HTTPException(422, "对象配置不可用")
        masks = {field["id"]: field["mask"] for field in SPEC["field_masks"][kind]}
        if not body.values or set(body.values) - set(masks):
            raise HTTPException(422, "字段未开放写入")
        values = {**current, **body.values}
        if body.object_type == 3:
            # Owner is changed only by teach/claim/delete; the UI writes enable/taught bits.
            point = state["points"][body.object_index]
            if point["owner"] is None:
                raise HTTPException(409, f"点位 {body.object_index} 是空闲槽，请先示教认领")
            requested = int(values["flags"])
            values["flags"] = point_flags(point["owner"], bool(requested & 1), bool(requested & 2))
        # JSON numeric fields arrive as numbers, but WORD fields must be exact integers.
        for key in ("flags", "delay_ms", "timeout_ms", "home_delay_ms"):
            if key in values and int(values[key]) == values[key]:
                values[key] = int(values[key])
        staging = record_encode(window, values)
        result = self.wait(worker.command(50, body.object_type, body.object_index,
                                     a=sum(masks[key] for key in body.values), b=body.epoch, staging=staging, session=body.session))
        return {**result, "readback": self.host.state()}

    def name_session(self, session):
        with self.host.lock:
            if not self.host.worker or self.host.worker.session != session:
                raise HTTPException(409, "会话已变化，请重新读取状态")
            return self.host.worker.state().get("binding_epoch")

    def save_name(self, body, name=None):
        kind = {1: "axis", 2: "cylinder", 3: "point"}[body.object_type]
        binding_epoch = self.name_session(body.session)
        try:
            entry = self.host.names.set(self.host.profile, kind, body.object_index, name, revision=body.revision,
                                   binding_epoch=binding_epoch)
        except NameConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True, "names": entry["names"], "revision": entry["revision"]}

    # Names are host metadata only: no Modbus write, no PLC ACK, no config_epoch change.
    def name(self, body: NameWriteRequest):
        return self.save_name(body, body.name)

    def delete_name(self, body: NameRequest):
        return self.save_name(body)

    def delete_point(self, index: int, body: SessionRequest):
        if not 0 <= index < POINTS:
            raise HTTPException(422, f"点位槽号 {index} 超出 0..{POINTS - 1}")
        worker = self.host.current(body.session)
        state = worker.state()
        point = state["points"][index]
        if point["owner"] is None:
            raise HTTPException(409, f"点位 {index} 已是空闲槽")
        if index == point["owner"]:
            raise HTTPException(409, f"点位 {index} 是轴 {index} 的待机点 P0，不能释放")
        if point["enabled"]:
            raise HTTPException(409, f"点位 {index} 仍处于启用状态，请先取消启用")
        staging = record_encode("points", {"position": point["position"], "speed": point["speed"], "flags": POINT_FREE})
        result = self.wait(worker.command(50, 3, index, a=4, b=state["config_epoch"], staging=staging, session=body.session))
        if result.get("result") == 0:
            self.host.names.set(self.host.profile, "point", index)
        return {**result, "readback": self.host.state()}

    def point(self, body: PointRequest):
        worker = self.host.current(body.session)
        return self.wait(worker.command(31, 1, body.axis, a=body.point, b=scaled(body.position), c=scaled(body.speed), session=body.session))

    def jog_start(self, body: JogStart, interaction_epoch=None):
        worker = self.host.current(body.session)
        with self.interaction_lock:
            if not self.interactive or interaction_epoch is not None and interaction_epoch != self.interaction_epoch:
                raise HTTPException(409, "窗口已失焦，请重新按下点动")
            future = worker.begin_jog(body.axis, body.direction, body.token, session=body.session)
        return self.wait(future)

    def jog_renew(self, body: JogToken, interaction_epoch=None):
        worker = self.host.current(body.session)
        with self.interaction_lock:
            if not self.interactive or interaction_epoch is not None and interaction_epoch != self.interaction_epoch:
                raise HTTPException(409, "窗口已失焦，点动租约已撤销")
            worker.renew_jog(body.token, session=body.session)
        return {"ok": True}

    def jog_stop(self, body: JogToken):
        future = self.host.current(body.session, stopping=True).end_jog(body.token, session=body.session)
        return self.wait(future) if future else {"result": 0, "message": "点动租约已撤销"}

