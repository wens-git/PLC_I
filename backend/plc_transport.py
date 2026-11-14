"""XJV1 transactions over a single Modbus connection, never an old-protocol shim."""
import time
from types import MappingProxyType

from .modbus_client import ModbusTcpClient
from .xj_protocol import (AXES, CYLINDERS, POINTS, REJECTIONS, SPEC, STATUS_OFFSET, WINDOWS,
                          SIGNATURE, address, decode_snapshot, dword, encode_command,
                          point_flags_valid, point_owner, record_decode, rejection_message,
                          split_dword)

# Newest rejection code published by the PLC; older hosts must be updated with it.
MAX_REJECTION = max(REJECTIONS)


class SnapshotUnavailable(RuntimeError):
    """Read-only publication race; no command write was attempted by this read."""


class PollInterrupted(RuntimeError):
    """A queued stop interrupted a read-only poll between Modbus requests."""


class PlcTransport:
    def __init__(self, host, port=SPEC["transport"]["port"], unit=SPEC["transport"]["unit"]):
        self.client = ModbusTcpClient(host, port, unit)
        self.heartbeat = 0
        self.last_heartbeat_write = 0
        self.cached_config = None
        self.cached_epoch = None
        self.cached_identity = None
        self.last_plc_heartbeat = None
        self.last_plc_change = time.monotonic()
        self.read_interrupt = None

    def _interrupt(self, interruptible):
        if interruptible and self.read_interrupt and self.read_interrupt():
            raise PollInterrupted("PLC poll interrupted by stop request")

    def read(self, window, index=None, deadline=None, interruptible=False):
        block = WINDOWS[window]
        count = block["stride"] if index is not None else block["stride"] * block["count"]
        base = address(window, index=index or 0)
        result = []
        for offset in range(0, count, 125):
            self._interrupt(interruptible)
            self._deadline(deadline)
            read = self.client.read_holding if block["area"] == "holding" else self.client.read_input
            result.extend(read(base + offset, min(125, count - offset)))
            self._deadline(deadline)
        return result

    @staticmethod
    def _deadline(deadline):
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("PLC批量读取超过1秒仍未完成，网络或PLC响应过慢")

    @staticmethod
    def _validate_status(status):
        if dword(status[:2]) != SIGNATURE:
            raise ConnectionError(f"PLC协议签名为 0x{dword(status[:2]):08X}，上位机要求 0x{SIGNATURE:08X}；"
                                  "请确认PLC程序已下载协议1.3版本")
        if status[STATUS_OFFSET["capacity"]] != 0x3610 or status[STATUS_OFFSET["point_pool"]] != POINTS:
            raise ConnectionError(f"PLC容量字 0x{status[STATUS_OFFSET['capacity']]:04X}/点位池 "
                                  f"{status[STATUS_OFFSET['point_pool']]} 与上位机(0x3610/{POINTS})不一致")
        axis_bound = status[STATUS_OFFSET["axis_bound"]]
        axis_online = STATUS_OFFSET["axis_online"]
        cylinder_bound = STATUS_OFFSET["cylinder_bound"]
        cylinder_online = STATUS_OFFSET["cylinder_online"]
        axis_summary = STATUS_OFFSET["axis_summary"]
        cylinder_summary = STATUS_OFFSET["cylinder_summary"]
        checks = (
            ("系统状态字含未定义位", status[STATUS_OFFSET["system"]] & ~0x7FF),
            ("未绑定轴被报告在线", status[axis_online] & ~axis_bound),
            ("气缸绑定位超出54路", dword(status[cylinder_bound:cylinder_bound + 4]) >> 54),
            ("未绑定气缸被报告在线", dword(status[cylinder_online:cylinder_online + 4])
             & ~dword(status[cylinder_bound:cylinder_bound + 4])),
            ("全局许可字含未定义位", status[STATUS_OFFSET["global_permit"]] & ~0x3FF),
            ("能力位含未定义位", status[STATUS_OFFSET["features"]] & ~3),
            ("ACK结果码超出0..%d" % MAX_REJECTION, status[STATUS_OFFSET["ack_result"]] > MAX_REJECTION),
            ("全局闭锁原因超出0..%d" % MAX_REJECTION, status[STATUS_OFFSET["global_reason"]] > MAX_REJECTION),
            ("最近拒绝码超出0..%d" % MAX_REJECTION, status[STATUS_OFFSET["last_rejection"]] > MAX_REJECTION),
        )
        for text, bad in checks:
            if bad:
                raise ValueError(f"PLC状态区数据非法：{text}（值 0x{int(bad):X}）")
        for index, value in enumerate(status[axis_summary:axis_summary + AXES]):
            if value & ~0xFF:
                raise ValueError(f"PLC状态区数据非法：轴 {index} 摘要字 0x{value:04X} 含未定义位")
        for index, value in enumerate(status[cylinder_summary:cylinder_summary + CYLINDERS]):
            if value & ~0x0F:
                raise ValueError(f"PLC状态区数据非法：气缸 {index} 摘要字 0x{value:04X} 含未定义位")

    def _coherent(self, windows=("status",), interruptible=False):
        deadline = time.monotonic() + 1
        for attempt in range(3):
            self._interrupt(interruptible)
            self._deadline(deadline)
            before = self.client.read_input(address("status", "snapshot_epoch"), 1)[0]
            self._deadline(deadline)
            if not before & 1:
                data = {name: self.read(name, deadline=deadline, interruptible=interruptible) for name in windows}
                self._interrupt(interruptible)
                after = self.client.read_input(address("status", "snapshot_epoch"), 1)[0]
                self._deadline(deadline)
                if (before == after and not after & 1
                        and data["status"][STATUS_OFFSET["snapshot_epoch"]] == after):
                    self._validate_status(data["status"])
                    return data
            if attempt < 2:
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        raise SnapshotUnavailable("PLC snapshot publication did not stabilize")

    def connect(self):
        self.close()
        try:
            return self._connect()
        except Exception:
            self.close()
            raise

    def _connect(self):
        self.client.connect()
        self._coherent()
        self.client.write_holding(address("command", "signature"), split_dword(SIGNATURE))
        self.heartbeat = (self.client.read_holding(address("command", "heartbeat"), 1)[0] + 1) & 65535
        self.client.write_single(address("command", "heartbeat"), self.heartbeat)
        self.last_heartbeat_write = time.monotonic()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            status = self._coherent()["status"]
            if status[STATUS_OFFSET["system"]] & 1:
                self.last_plc_heartbeat = status[2]
                self.last_plc_change = time.monotonic()
                # The PLC adopts whatever SEQ sits in Holding word 4 as its consumed
                # baseline when the HMI comes online, and only executes a different
                # SEQ. Seed from that word (not the published ACK SEQ, which can lag
                # it after a PLC restart) so the next SEQ can never equal the baseline.
                return self.client.read_holding(address("command", "commit"), 1)[0]
            time.sleep(0.02)
        raise TimeoutError("PLC未确认HMI在线")

    def tick(self, elapsed):
        if time.monotonic() - self.last_heartbeat_write >= 0.8:
            self.heartbeat = (self.heartbeat + 1) & 65535
            self.client.write_single(address("command", "heartbeat"), self.heartbeat)
            self.last_heartbeat_write = time.monotonic()

    def _live(self):
        data = self._coherent(("status", "axis_live", "cylinder_live", "io"), interruptible=True)
        status = data["status"]
        if status[2] != self.last_plc_heartbeat:
            self.last_plc_change = time.monotonic()
            self.last_plc_heartbeat = status[2]
        if time.monotonic() - self.last_plc_change > 1.5:
            raise TimeoutError("PLC心跳停止")
        state = decode_snapshot(data)
        if not state["handshake"] or not state["online"]:
            raise ConnectionError("PLC握手或HMI在线状态失效")
        axis_bound = status[STATUS_OFFSET["axis_bound"]]
        axis_summary = STATUS_OFFSET["axis_summary"]
        for index in range(AXES):
            block = data["axis_live"][index * 16:(index + 1) * 16]
            if block[6] & ~0x1FFF or block[7] > MAX_REJECTION or block[12] > 4 or block[13] & ~15 or any(block[14:]):
                raise ValueError(f"PLC发布的轴 {index} 实时数据非法（许可/原因/结果/限位字超出定义）")
            if not axis_bound & (1 << index) and (status[axis_summary + index] or block[6]):
                raise ValueError(f"轴 {index} 未绑定却发布了状态或许可，请核对PLC绑定表")
        bound = dword(status[STATUS_OFFSET["cylinder_bound"]:STATUS_OFFSET["cylinder_bound"] + 4])
        cylinder_summary = STATUS_OFFSET["cylinder_summary"]
        for index in range(CYLINDERS):
            block = data["cylinder_live"][index * 3:(index + 1) * 3]
            if block[0] & ~15 or block[1] > MAX_REJECTION:
                raise ValueError(f"PLC发布的气缸 {index} 实时数据非法（许可/原因超出定义）")
            if not bound & (1 << index) and (status[cylinder_summary + index] or block[0]):
                raise ValueError(f"气缸 {index} 未绑定却发布了状态或许可，请核对PLC绑定表")
        io = data["io"]
        if io[0] > 128 or io[1] > 128 or any(io[18:]):
            raise ValueError(f"PLC发布的IO数量非法（X={io[0]}, Y={io[1]}，上限128）或保留字非零")
        for start, count in ((2, io[0]), (10, io[1])):
            if any(io[start + bit // 16] & (1 << (bit % 16)) for bit in range(count, 128)):
                raise ValueError("PLC发布的IO位超出其声明的点数")
        return data, state

    @staticmethod
    def _validate_config(config, status):
        axis_bound = status[STATUS_OFFSET["axis_bound"]]
        features = status[STATUS_OFFSET["features"]]
        for index in range(AXES):
            block = config["axis_config"][index * 16:(index + 1) * 16]
            if block[14] & ~1 or block[15]:
                raise ValueError(f"轴 {index} 参数的保留位非零")
            if axis_bound & (1 << index):
                if dword(block[2:4], True) >= dword(block[:2], True):
                    raise ValueError(f"轴 {index} 软负限位不小于软正限位")
                if any(not 1 <= dword(block[offset:offset + 2]) <= 0x7FFFFFFF for offset in range(4, 14, 2)):
                    raise ValueError(f"轴 {index} 速度或加减速度为 0 或超出范围")
        bound = dword(status[STATUS_OFFSET["cylinder_bound"]:STATUS_OFFSET["cylinder_bound"] + 4])
        for index in range(CYLINDERS):
            block = config["cylinder_config"][index * 8:(index + 1) * 8]
            if block[0] & ~0x0F:
                raise ValueError(f"气缸 {index} 参数含不支持的标志位")
            mode = block[0] & 3
            if any(value != 65535 and not 0 <= value < 128 for value in block[1:5]):
                raise ValueError(f"气缸 {index} IO映射非法")
            if mode in (0, 2) and block[2] != 65535:
                raise ValueError(f"气缸 {index} 单输出模式不能映射原点输出")
            if bound & (1 << index):
                if block[1] == 65535 or mode in (1, 3) and block[2] == 65535:
                    raise ValueError(f"气缸 {index} 输出未映射")
                if (not 0 <= block[5] < block[6] <= 65535 or
                        not 0 <= block[7] < block[6] or
                        block[3] == 65535 and not block[5] or block[4] == 65535 and not block[7]):
                    raise ValueError(f"气缸 {index} 延时/超时非法（无传感器延时须大于0，且两侧延时均小于超时）")
        for index in range(POINTS):
            block = config["points"][index * 5:(index + 1) * 5]
            if not point_flags_valid(block[4]):
                raise ValueError(f"点位 {index} 标志字 0x{block[4]:04X} 非法")
            owner = point_owner(block[4])
            if owner is not None and axis_bound & (1 << owner) and not 1 <= dword(block[2:4]) <= 0x7FFFFFFF:
                raise ValueError(f"点位 {index} 速度为 0 或超出范围")

    def snapshot(self):
        data, state = self._live()
        status = data["status"]
        identity = (status[STATUS_OFFSET["binding_epoch"]], status[STATUS_OFFSET["axis_bound"]],
                    *status[STATUS_OFFSET["cylinder_bound"]:STATUS_OFFSET["cylinder_bound"] + 4],
                    status[STATUS_OFFSET["features"]])
        if self.cached_epoch != status[STATUS_OFFSET["config_epoch"]] or self.cached_identity != identity:
            config = {}
            deadline = time.monotonic() + 1
            self._interrupt(True)
            baseline = self.client.read_input(address("status", "config_epoch"), 1)[0]
            if baseline != status[STATUS_OFFSET["config_epoch"]]:
                raise SnapshotUnavailable("Configuration changed before read")
            for name in ("axis_config", "cylinder_config", "points"):
                config[name] = self.read(name, deadline=deadline, interruptible=True)
                self._interrupt(True)
                self.tick(0)
            self._interrupt(True)
            after = self.client.read_input(address("status", "config_epoch"), 1)[0]
            self._deadline(deadline)
            if after != baseline:
                raise SnapshotUnavailable("配置读取期间纪元变化")
            self._validate_config(config, status)
            # A bulk configuration read must not age the permissions being published.
            data, state = self._live()
            current = data["status"]
            if (current[STATUS_OFFSET["config_epoch"]] != baseline
                    or (current[STATUS_OFFSET["binding_epoch"]], current[STATUS_OFFSET["axis_bound"]],
                        *current[STATUS_OFFSET["cylinder_bound"]:STATUS_OFFSET["cylinder_bound"] + 4],
                        current[STATUS_OFFSET["features"]]) != identity):
                raise SnapshotUnavailable("Configuration or binding changed after read")
            self.cached_config = MappingProxyType({name: tuple(words) for name, words in config.items()})
            self.cached_epoch = baseline
            self.cached_identity = identity
        config = self.cached_config
        pool = []
        for slot in range(POINTS):
            rec = record_decode("points", config["points"][slot * 5:(slot + 1) * 5])
            pool.append({**rec, "index": slot, "owner": point_owner(int(rec["flags"])),
                         "enabled": bool(rec["flags"] & 1), "taught": bool(rec["flags"] & 2)})
        state["points"] = pool
        for axis in state["axes"]:
            index = axis["index"]
            axis["config"] = record_decode("axis_config", config["axis_config"][index * 16:(index + 1) * 16])
            axis["points"] = [point for point in pool if point["owner"] == index]
        for cylinder in state["cylinders"]:
            index = cylinder["index"]
            cylinder["config"] = record_decode("cylinder_config", config["cylinder_config"][index * 8:(index + 1) * 8])
        io = data["io"]
        if io[0] > 128 or io[1] > 128:
            raise ValueError("PLC发布非法IO容量")
        state["io"] = {name: [bool(io[start + i // 16] & (1 << (i % 16))) for i in range(count)]
                       for name, start, count in (("x", 2, io[0]), ("y", 10, io[1]))}
        state["raw"] = data
        return state

    def submit(self, cmd):
        baseline = self._coherent()["status"][6]
        frame = encode_command(cmd, self.heartbeat)
        self.client.write_holding(address("command", "object"), frame[5:12])
        self.client.write_holding(address("command", "staging"), frame[16:32])
        self.client.write_single(address("command", "code"), cmd.code)
        self.client.write_single(address("command", "commit"), cmd.sequence)
        return baseline

    def ack(self, cmd, baseline):
        status = self._coherent()["status"]
        if (status[3] == cmd.sequence and status[5] == cmd.object_word
                and status[STATUS_OFFSET["ack_epoch"]] != baseline):
            return {"result": status[4], "message": rejection_message(status[4]), "seq": cmd.sequence,
                    "object": status[5], "ack_epoch": status[STATUS_OFFSET["ack_epoch"]]}
        return None

    def renew_jog(self, object_word, seq, counter):
        self.client.write_holding(address("command", "jog_renew"), [counter, object_word, seq])

    def close(self):
        self.client.close()
        self.cached_config = self.cached_epoch = None
        self.cached_identity = None
        self.last_plc_heartbeat = None
