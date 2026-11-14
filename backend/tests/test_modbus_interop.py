"""Interoperability over real Modbus TCP: official pymodbus client <-> pymodbus server.

The server stands in for the PLC's official ModbusTCP slave device: separate
Holding (32) and Input (1830) areas, zero-based. Python lists are the register
images; the server action copies them in/out on every request and emulates only
the PLC-side protocol behaviour needed here (online bit, SEQ -> ACK). This proves
the production client talks standard Modbus TCP; it is not PLC acceptance.
The test binds a free loopback port; production uses 1502.
"""
import asyncio
import socket
import threading
import time
import unittest

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from backend.plc_transport import PlcTransport
from backend.xj_protocol import (POINT_FREE, POINTS, SPEC, STATUS_OFFSET, WINDOWS, Command, address,
                                 record_encode, split_dword)

HOLDING = SPEC["areas"]["holding"]
INPUT = SPEC["areas"]["input"]
STATUS = address("status")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class FakePlc:
    def __init__(self):
        self.lock = threading.Lock()
        self.holding = [0] * HOLDING
        self.input = [0] * INPUT
        self.input_writes = 0
        self.last_seq = None
        self.last_heartbeat = None
        status = [0] * WINDOWS["status"]["stride"]
        status[:2] = split_dword(SPEC["signature"])
        status[STATUS_OFFSET["capacity"]] = 0x3610
        status[STATUS_OFFSET["axis_bound"]] = 7
        status[STATUS_OFFSET["axis_online"]] = 7
        status[STATUS_OFFSET["point_pool"]] = POINTS
        self.put("status", status)
        axis = record_encode("axis_config", dict(positive_limit=100, negative_limit=-100, manual_speed=1,
                                                 auto_speed=2, acceleration=3, deceleration=3,
                                                 estop_deceleration=5, flags=1))
        self.put("axis_config", axis * 16)
        self.put("cylinder_config", [0, 65535, 65535, 65535, 65535, 200, 3000, 0] * 54)
        points = [0, 0, 0, 1000, POINT_FREE] * POINTS
        points[4] = 15 << 2  # slot 0 owned by axis 15, the former "free" code
        self.put("points", points)

    def put(self, window, values):
        base = address(window)
        self.input[base:base + len(values)] = values

    def device(self):
        blocks = ([SimData(0, 1, False, DataType.BITS)], [SimData(0, 1, False, DataType.BITS)],
                  [SimData(0, HOLDING, 0, DataType.REGISTERS)], [SimData(0, INPUT, 0, DataType.REGISTERS)])
        return SimDevice(SPEC["transport"]["unit"], simdata=blocks, action=self.action)

    def _plc_scan(self):
        command = self.holding
        signature_ok = command[:2] == split_dword(SPEC["signature"])
        heartbeat = self.input[STATUS + STATUS_OFFSET["heartbeat"]]
        self.input[STATUS + STATUS_OFFSET["heartbeat"]] = (heartbeat + 1) & 0xFFFF
        if signature_ok and command[2] != self.last_heartbeat:
            self.input[STATUS + STATUS_OFFSET["system"]] = 1
        self.last_heartbeat = command[2]
        seq = command[4]
        if self.last_seq is None:
            self.last_seq = seq
        elif seq and seq != self.last_seq:
            self.last_seq = seq
            result = 0 if command[3] == 20 and (command[5] & 0xFF) < 3 else 4
            epoch = (self.input[STATUS + STATUS_OFFSET["ack_epoch"]] + 1) & 0xFFFF
            base = STATUS + STATUS_OFFSET["ack_seq"]
            self.input[base:base + 4] = [seq, result, command[5], epoch]

    async def action(self, function_code, start_address, req_address, count, registers, set_values):
        with self.lock:
            if function_code in (3, 6, 16):
                if set_values is not None:
                    offset = req_address - start_address
                    self.holding[offset:offset + len(set_values)] = list(set_values)
                registers[:] = self.holding
            elif function_code == 4:
                self._plc_scan()
                registers[:] = self.input
            else:
                self.input_writes += 1
        return None


class ModbusInteropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plc = FakePlc()
        cls.port = free_port()
        cls.loop = asyncio.new_event_loop()
        started = threading.Event()

        def serve():
            async def main():
                # The server must be constructed inside its running event loop.
                cls.server = ModbusTcpServer(cls.plc.device(), address=("127.0.0.1", cls.port))
                started.set()
                await cls.server.serve_forever()
            asyncio.set_event_loop(cls.loop)
            cls.loop.run_until_complete(main())

        cls.thread = threading.Thread(target=serve, daemon=True)
        cls.thread.start()
        started.wait(5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        asyncio.run_coroutine_threadsafe(cls.server.shutdown(), cls.loop).result(5)
        cls.thread.join(5)

    def setUp(self):
        self.transport = PlcTransport("127.0.0.1", self.port)

    def tearDown(self):
        self.transport.close()

    def test_default_port_is_1502(self):
        self.assertEqual(PlcTransport("127.0.0.1").client.client.comm_params.port, 1502)

    def test_handshake_snapshot_and_command_ack_over_tcp(self):
        self.transport.connect()
        self.assertEqual(self.plc.holding[:2], split_dword(SPEC["signature"]))
        state = self.transport.snapshot()
        self.assertEqual(len(state["points"]), POINTS)
        self.assertEqual(state["points"][0]["owner"], 15)
        self.assertIsNone(state["points"][1]["owner"])
        cmd = Command(20, 1, 0, sequence=self.plc.holding[4] % 65535 + 1)
        baseline = self.transport.submit(cmd)
        self.assertEqual(self.plc.holding[4], cmd.sequence)  # SEQ is written last
        deadline = time.monotonic() + 2
        ack = None
        while ack is None and time.monotonic() < deadline:
            ack = self.transport.ack(cmd, baseline)
        self.assertIsNotNone(ack)
        self.assertEqual(ack["result"], 0)

    def test_input_area_is_read_only_for_the_host(self):
        self.transport.connect()
        before = list(self.plc.input[address("points"):address("points") + 10])
        self.transport.snapshot()
        self.assertEqual(self.plc.input[address("points"):address("points") + 10], before)
        self.assertEqual(self.plc.input_writes, 0)


if __name__ == "__main__":
    unittest.main()
