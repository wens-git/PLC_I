"""Single-owner transport loop: stops, deadman, ACK, commands, then polling."""
import time
import uuid
from collections import deque
from concurrent.futures import Future
from dataclasses import replace
from threading import Event, RLock, Thread

from .tags import Tags
from .plc_transport import PollInterrupted, SnapshotUnavailable
from .xj_protocol import (Command, SPEC, alarm_detail, command_name, object_label, point_flags,
                          record_decode, rejection_action, scaled, validate_command)

STOP_CODES = {9, 10, 26, 42}


class CommWorker:
    def __init__(self, transport, mode="mock", poll_interval=0.1, names=None):
        self.transport, self.mode, self.poll_interval = transport, mode, poll_interval
        self.names = names  # callable returning the host name store; display only
        self.active_alarms = {}
        self.tags = Tags()
        self.session = uuid.uuid4().hex
        self.lock = RLock()
        self.queue, self.stops = deque(), deque()
        self.wake, self.shutdown = Event(), Event()
        self.thread = None
        self.pending = None
        self.jog = None
        self.sequence = 0
        self.ready = mode == "mock"
        self.last_poll = 0
        self.next_connect = 0
        self.failures = 0
        self.closing = False
        self.stale_since = None
        if mode == "tcp":
            self.transport.read_interrupt = lambda: bool(self.stops) or self.shutdown.is_set()

    def start(self):
        self.thread = Thread(target=self._loop, name="xj-comm", daemon=True)
        self.thread.start()

    def state(self):
        result = self.tags.snapshot()
        result.update(mode=self.mode, session=self.session)
        return result

    def _finish(self, entry, result=None, error=None):
        future = entry[1]
        if error is not None and not future.done():
            # Every command that ends without an ACK leaves a concrete history line.
            self._command_event(entry[0], error=error)
        if not future.done():
            if error:
                future.set_exception(RuntimeError(str(error)))
            else:
                future.set_result(result)

    def _session_check(self, session):
        if session is not None and (session != self.session or not self.ready):
            raise RuntimeError("会话已失效，命令未发送；请刷新状态后重试")

    def command(self, code, object_type=0, object_index=0, a=0, b=0, c=0, staging=(), session=None):
        cmd = Command(code, object_type, object_index, a, b, c, staging=tuple(staging))
        validate_command(cmd)
        future = Future()
        entry = (cmd, future, time.monotonic())
        with self.lock:
            self._session_check(session)
            if self.closing and code not in STOP_CODES:
                raise RuntimeError("连接正在关闭，仅允许停止命令")
            if self.shutdown.is_set():
                raise RuntimeError("连接已关闭")
            if code in STOP_CODES:
                for item in self.queue:
                    self._finish(item, error="被停止请求取消，未发送")
                self.queue.clear()
                if code in (9, 10) or (self.jog and (self.jog.get("seq") is None or code == 26 and object_index == self.jog["axis"])):
                    self.jog = None
                self.stops.append(entry)
            else:
                if len(self.queue) >= 32:
                    raise RuntimeError("命令队列已满")
                self.queue.append(entry)
        self.wake.set()
        return future

    def begin_jog(self, axis, direction, token, session=None):
        if direction not in (-1, 1) or not token:
            raise ValueError("点动方向或令牌非法")
        with self.lock:
            self._session_check(session)
            if self.jog:
                raise RuntimeError("已有点动会话，请先停止")
            self.jog = {"axis": axis, "token": token, "proof": time.monotonic(), "seq": None, "counter": 0, "renew": 0}
            try:
                return self.command(24 if direction == 1 else 25, 1, axis)
            except Exception:
                self.jog = None
                raise

    def renew_jog(self, token, session=None):
        with self.lock:
            self._session_check(session)
            if self.jog and self.jog["token"] == token:
                self.jog["proof"] = time.monotonic()

    def end_jog(self, token=None, session=None):
        with self.lock:
            self._session_check(session)
            if self.jog and (token is None or self.jog["token"] == token):
                axis = self.jog["axis"]
                self.jog = None
                return self.command(26, 1, axis)

    def stop(self):
        with self.lock:
            self.closing = True
            future = self.end_jog()
            for entry in self.queue:
                self._finish(entry, error="连接正在关闭，命令未发送")
            self.queue.clear()
        if future and self.thread and self.thread.is_alive():
            try:
                future.result(timeout=2)
            except Exception:
                pass  # PLC lease remains the fallback if the network is unavailable.
        self.shutdown.set()
        self.wake.set()
        if self.thread:
            self.thread.join(5)
            if self.thread.is_alive():
                raise RuntimeError("通信线程尚未退出，禁止建立第二连接")

    def _publish(self):
        state = self.transport.snapshot()
        state.update(error="", updated=time.time())
        self._alarm_events(state)
        self.tags.publish(state)
        self.last_poll = time.monotonic()
        self.failures = 0
        self.stale_since = None

    def _lost(self, exc):
        with self.lock:
            self.ready = False
            self.jog = None
            self.session = uuid.uuid4().hex
            if self.pending:
                self._finish(self.pending[0], error=f"通信中断，已发送命令结果未知（{exc}）；请到现场确认对象状态")
                self.pending = None
            for entry in (*self.queue, *self.stops):
                self._finish(entry, error="连接已失效，命令未重放")
            self.queue.clear()
            self.stops.clear()
        old = self.tags.snapshot()
        old.update(connected=False, handshake=False, error=str(exc))
        self.tags.publish(old)
        self.tags.event(f"PLC通信中断：{exc}", level="error", category="link", detail=type(exc).__name__,
                        action="检查网线、PLC运行状态和IP/端口；恢复后需重新握手，未完成命令不会重放", source="HMI")
        self.transport.close()
        self.next_connect = time.monotonic() + 1

    def _ack_complete(self, entry, result):
        cmd = entry[0]
        if cmd.code in (24, 25):
            with self.lock:
                if self.jog and self.jog.get("submitted") == cmd.sequence:
                    if result["result"] == 0:
                        self.jog["seq"] = cmd.sequence
                    else:
                        self.jog = None
        self._command_event(cmd, result)
        # The client sees an ACK and the post-command snapshot together.
        try:
            self._publish()
            if result["result"] == 0:
                self._verify_readback(cmd)
        except Exception as exc:
            self._finish(entry, error=f"PLC已受理，但状态回读失败：{exc}")
            raise
        self._finish(entry, result=result)

    def _command_event(self, cmd, result=None, error=None):
        """Concrete history line: which command, on which object, with what outcome and remedy."""
        names = self.names() if self.names else {}
        subject = f"{command_name(cmd.code)} · {object_label(cmd.object_word, names)}"
        fields = dict(code=cmd.code, command=command_name(cmd.code), object=cmd.object_word,
                      object_label=object_label(cmd.object_word, names), seq=cmd.sequence, source="HMI")
        if error is not None:
            self.tags.event(f"{subject}：{error}", level="error", category="command", detail=str(error), **fields)
        elif result["result"] == 0:
            self.tags.event(f"{subject}：PLC已受理", level="ok", category="command", result=0, **fields)
        else:
            self.tags.event(f"{subject}：被拒绝（{result['result']} {result['message']}）", level="error",
                            category="command", result=result["result"], reason=result["message"],
                            action=rejection_action(result["result"]), **fields)

    def _alarm_events(self, state):
        """Log alarm raise/clear edges with the concrete cause, not just a code."""
        current = {(a["object"], a["code"]): a for a in state.get("alarms", [])}
        names = self.names() if self.names else {}
        for key, alarm in current.items():
            if key not in self.active_alarms:
                self.tags.event(f"报警 {alarm['code']} · {object_label(alarm['object'], names)}：{alarm['message']}",
                                level="error", category="alarm", object=alarm["object"], alarm=alarm["code"],
                                object_label=object_label(alarm["object"], names), action=alarm["action"], source="PLC")
        for key in self.active_alarms.keys() - current.keys():
            self.tags.event(f"报警解除 {key[1]} · {object_label(key[0], names)}：{alarm_detail(key[1])['message']}",
                            level="ok", category="alarm", object=key[0], alarm=key[1], source="PLC")
        self.active_alarms = current

    def _verify_readback(self, cmd):
        if cmd.code not in (31, 50):
            return
        state = self.state()
        if cmd.code == 31:
            point = state["points"][cmd.a]
            matches = (point["owner"] == cmd.object_index and point["taught"]
                       and scaled(point["position"]) == cmd.b and scaled(point["speed"]) == cmd.c)
        else:
            if cmd.object_type == 3:
                target = state["points"][cmd.object_index]
            else:
                target = state["axes" if cmd.object_type == 1 else "cylinders"][cmd.object_index]
            kind = {1: "axis", 2: "cylinder", 3: "point"}[cmd.object_type]
            window = {1: "axis_config", 2: "cylinder_config", 3: "points"}[cmd.object_type]
            expected = record_decode(window, cmd.staging)
            if cmd.object_type == 3:
                actual = {**target, "flags": point_flags(target["owner"], target["enabled"], target["taught"])}
            else:
                actual = target["config"]
            matches = all(actual[field["id"]] == expected[field["id"]]
                          for field in SPEC["field_masks"][kind] if field["mask"] & cmd.a)
        if not matches:
            raise RuntimeError("PLC已受理，但回读值与提交值不一致；请核对参数，禁止自动重试")

    def _loop(self):
        last = time.monotonic()
        try:
            while not self.shutdown.is_set():
                now = time.monotonic()
                elapsed, last = now - last, now
                try:
                    if not self.ready:
                        if now < self.next_connect:
                            self.wake.wait(0.05)
                            self.wake.clear()
                            continue
                        self.sequence = self.transport.connect() or 0
                        self.ready = True
                        self.tags.event("PLC协议握手完成", level="ok", category="link", source="HMI")
                    if not self.stops:
                        self.transport.tick(elapsed)
                    now = time.monotonic()
                    with self.lock:
                        jog = self.jog
                        if jog and now - jog["proof"] > 0.4:
                            self.end_jog(jog["token"])
                        elif jog and not self.stops and jog["seq"] is not None and now - jog["renew"] >= 0.2:
                            jog["counter"] = (jog["counter"] + 1) & 65535
                            self.transport.renew_jog(0x100 | jog["axis"], jog["seq"], jog["counter"])
                            jog["renew"] = now
                        if self.stops and self.pending:
                            self._finish(self.pending[0], error="被停止抢占，已发送动作结果未知")
                            self.pending = None
                        entry = self.stops.popleft() if self.stops else self.queue.popleft() if self.queue and not self.pending else None
                    if entry:
                        with self.lock:
                            cmd = entry[0]
                            if cmd.code not in STOP_CODES and (self.stops or self.closing):
                                self._finish(entry, error="发送前被停止请求取消，未发送")
                                continue
                            if cmd.code in (24, 25) and (time.monotonic() - entry[2] > 0.4 or not self.jog):
                                self._finish(entry, error="点动按住证明已过期，未发送")
                                continue
                            self.sequence = self.sequence % 65535 + 1
                            cmd = replace(cmd, sequence=self.sequence)
                            entry = (cmd, entry[1], entry[2])
                            if cmd.code in (24, 25):
                                self.jog["submitted"] = cmd.sequence
                            if self.mode == "mock":
                                result = self.transport.command(cmd.code, cmd.object_type, cmd.object_index,
                                                                cmd.a, cmd.b, cmd.c, staging=cmd.staging, sequence=cmd.sequence)
                                self._ack_complete(entry, result)
                            else:
                                # Serialize admission with dispatch; a lost write is never retried.
                                self.pending = (entry, None, now + (10 if cmd.code == 53 else 1))
                                baseline = self.transport.submit(cmd)
                                self.pending = (entry, baseline, time.monotonic() + (10 if cmd.code == 53 else 1))
                    if self.pending:
                        entry, baseline, deadline = self.pending
                        result = self.transport.ack(entry[0], baseline)
                        if result is not None:
                            self.pending = None
                            self._ack_complete(entry, result)
                        elif time.monotonic() > deadline:
                            raise TimeoutError("ACK超时，结果未知，禁止自动重试")
                    elif time.monotonic() - self.last_poll >= self.poll_interval:
                        self._publish()
                except Exception as exc:
                    if self.mode == "tcp" and isinstance(exc, (PollInterrupted, SnapshotUnavailable)):
                        # A missing baseline means submit performed no writes; never replay it.
                        if self.pending and self.pending[1] is None:
                            self._finish(self.pending[0], error="未取得一致的PLC状态快照，命令未发送")
                            self.pending = None
                        if isinstance(exc, SnapshotUnavailable):
                            self.stale_since = self.stale_since or time.monotonic()
                            expired_ack = self.pending and time.monotonic() > self.pending[2]
                            if expired_ack or time.monotonic() - self.stale_since > 1.5:
                                self._lost(exc)
                    elif self.mode == "tcp":
                        self._lost(exc)
                    else:
                        if not ('entry' in locals() and entry):
                            self.tags.event(f"模拟PLC异常：{exc}", level="error", category="link", source="HMI")
                        if 'entry' in locals() and entry:
                            self._finish(entry, error=exc)
                self.wake.wait(0.01)
                self.wake.clear()
        finally:
            # Cancel queued work on exit. Never replay it on a new connection.
            with self.lock:
                for entry in (*self.queue, *self.stops):
                    self._finish(entry, error="连接关闭，命令已取消")
                if self.pending:
                    self._finish(self.pending[0], error="连接关闭，已发送命令结果未知")
            if hasattr(self.transport, "close"):
                self.transport.close()
