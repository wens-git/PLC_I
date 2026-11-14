import json
import socket
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ProtocolRuntimeTests(unittest.TestCase):
    def test_command_and_status_round_trip(self):
        from backend.xj_protocol import Command, decode_snapshot, encode_command

        frame = encode_command(Command(20, object_type=1, object_index=0, sequence=7), 3)
        self.assertEqual(frame[0:2], [0x584A, 0x5633])
        self.assertEqual(frame[3], 20)
        self.assertEqual(frame[4], 7)
        self.assertEqual(frame[5], 0x0100)

        snapshot = decode_snapshot({"status": [0] * 104})
        self.assertFalse(snapshot["connected"])
        self.assertEqual(len(snapshot["axes"]), 16)
        self.assertEqual(len(snapshot["cylinders"]), 54)

    def test_system_word_bit8_publishes_reset_required(self):
        from backend.xj_protocol import decode_snapshot

        status = [0] * 104
        status[7] = 1 | 256  # bit0 HMI在线 + bit8 确认后待复位
        snapshot = decode_snapshot({"status": status})
        self.assertTrue(snapshot["online"])
        self.assertTrue(snapshot["reset_required"])
        status[7] = 1
        self.assertFalse(decode_snapshot({"status": status})["reset_required"])

    def test_system_word_bit10_publishes_paused(self):
        from backend.xj_protocol import decode_snapshot

        status = [0] * 104
        status[7] = 1 | 1024  # bit0 HMI在线 + bit10 已暂停
        snapshot = decode_snapshot({"status": status})
        self.assertTrue(snapshot["online"])
        self.assertTrue(snapshot["paused"])
        status[7] = 1
        self.assertFalse(decode_snapshot({"status": status})["paused"])

    def test_transport_status_validation_accepts_paused_bit(self):
        from backend.plc_transport import PlcTransport

        status = [0] * 104
        status[0:2] = [0x584A, 0x5633]
        status[7] = 1 | 4 | 1024  # 在线 + 运行 + 已暂停
        status[8] = 0x3610
        status[102] = 120
        PlcTransport._validate_status(status)
        status[7] |= 2048  # bit11 未定义
        with self.assertRaises(ValueError):
            PlcTransport._validate_status(status)

    def test_transport_accepts_every_published_rejection_code(self):
        """Detailed 20..28 codes must not be rejected as corrupt status words."""
        from backend.plc_transport import MAX_REJECTION, PlcTransport
        from backend.xj_protocol import STATUS_OFFSET

        status = [0] * 104
        status[0:2] = [0x584A, 0x5633]
        status[7] = 1
        status[8] = 0x3610
        status[102] = 120
        for key in ("ack_result", "global_reason", "last_rejection"):
            status[STATUS_OFFSET[key]] = MAX_REJECTION
        PlcTransport._validate_status(status)
        self.assertEqual(MAX_REJECTION, 28)
        status[STATUS_OFFSET["ack_result"]] = MAX_REJECTION + 1
        with self.assertRaises(ValueError):
            PlcTransport._validate_status(status)

    def test_client_uses_official_pymodbus_api_only(self):
        """No hand-built Modbus ADU helpers may exist in the production client."""
        import backend.modbus_client as client
        source = (ROOT / "backend/modbus_client.py").read_text(encoding="utf-8")
        self.assertIn("from pymodbus.client import ModbusTcpClient", source)
        for forbidden in ("build_read_request", "build_write_single_request", "struct.pack", "import socket"):
            self.assertNotIn(forbidden, source)
        self.assertEqual(client.ModbusTcpClient.__init__.__defaults__[0], 1502)


class MockPlcTests(unittest.TestCase):
    def setUp(self):
        from backend.mock_plc import MockPlc
        self.plc = MockPlc()

    def test_enable_and_unbound_rejection(self):
        ok = self.plc.command(20, 1, 0)
        bad = self.plc.command(20, 1, 4)
        self.assertEqual(ok["result"], 0)
        self.assertEqual(bad["result"], 4)
        self.assertTrue(self.plc.snapshot()["axes"][0]["enabled"])

    def test_jog_changes_position_and_stop_is_idempotent(self):
        self.plc.command(20, 1, 0)
        self.plc.command(24, 1, 0)
        before = self.plc.snapshot()["axes"][0]["position"]
        self.plc.tick(0.2)
        after = self.plc.snapshot()["axes"][0]["position"]
        self.assertGreater(after, before)
        self.assertEqual(self.plc.command(26, 1, 0)["result"], 0)
        self.assertEqual(self.plc.command(26, 1, 0)["result"], 0)

    def test_estop_rejects_motion_and_reset_clears_it(self):
        self.plc.command(10, 0, 0)
        self.assertEqual(self.plc.command(20, 1, 0)["result"], 3)
        self.plc.command(11, 0, 0)
        self.assertEqual(self.plc.command(20, 1, 0)["result"], 0)


class WorkerTests(unittest.TestCase):
    def test_command_is_processed_before_poll(self):
        from backend.comm_worker import CommWorker
        from backend.mock_plc import MockPlc

        plc = MockPlc()
        worker = CommWorker(plc, mode="mock", poll_interval=0.02)
        worker.start()
        try:
            result = worker.command(20, 1, 0).result(timeout=1)
            self.assertEqual(result["result"], 0)
            state = worker.state()
            self.assertTrue(state["axes"][0]["enabled"])
        finally:
            worker.stop()


if __name__ == "__main__":
    unittest.main()
