import time
import unittest


class CodecSafetyTests(unittest.TestCase):
    def test_retired_name_command_is_not_encodable(self):
        from backend.xj_protocol import Command, encode_command
        with self.assertRaises(ValueError):
            encode_command(Command(51, 1, 0), 1)

    def test_command_rejects_invalid_object_or_numeric_wrap(self):
        from backend.xj_protocol import Command, encode_command
        for cmd in (Command(20, 1, -1), Command(20, 1, 16), Command(27, 1, 0, a=2**31),
                    Command(27, 1, 0, a=1, b=-1), Command(99), Command(20, 2, 0)):
            with self.subTest(cmd=cmd), self.assertRaises(ValueError):
                encode_command(cmd, 1)

    def test_scale_is_exact(self):
        from backend.xj_protocol import scaled
        self.assertEqual(scaled("-12.345"), -12345)
        for value in ("nan", "inf", "0.0001", "2147483.648"):
            with self.assertRaises(ValueError):
                scaled(value)


class WorkerSafetyTests(unittest.TestCase):
    def test_other_axis_stop_does_not_discard_active_jog(self):
        from backend.comm_worker import CommWorker
        worker = CommWorker(object())
        worker.jog = {"axis": 0, "seq": 10, "token": "active"}
        worker.command(26, 1, 1)
        self.assertEqual(worker.jog["axis"], 0)

    def test_cylinder_stop_cancels_unsent_jog_proof(self):
        from backend.comm_worker import CommWorker
        worker = CommWorker(object())
        worker.begin_jog(0, 1, "pending")
        worker.command(42, 2, 0)
        self.assertIsNone(worker.jog)

    def test_stale_session_rejected_at_enqueue(self):
        from backend.comm_worker import CommWorker
        worker = CommWorker(object(), mode="mock")
        with self.assertRaises(RuntimeError):
            worker.command(20, 1, 0, session="old-session")
        self.assertFalse(worker.queue)

    def test_ack_readback_failure_is_not_success(self):
        from concurrent.futures import Future
        from backend.comm_worker import CommWorker
        from backend.xj_protocol import Command
        class Broken:
            def snapshot(self):
                raise OSError("readback lost")
        worker = CommWorker(Broken())
        future = Future()
        with self.assertRaises(OSError):
            worker._ack_complete((Command(50, 1, 0), future, 0), {"result": 0, "message": "accepted"})
        with self.assertRaises(RuntimeError):
            future.result(0.1)

    def test_parameter_ack_must_match_readback(self):
        from concurrent.futures import Future
        from backend.comm_worker import CommWorker
        from backend.xj_protocol import Command, record_encode
        staging = record_encode("cylinder_config", dict(wiring_flags=0, move_y=1, home_y=2, move_x=1, home_x=2,
                                                        delay_ms=100, timeout_ms=3000, home_delay_ms=0))
        class Wrong:
            def snapshot(self):
                return {"cylinders": [{"config": dict(wiring_flags=0, move_y=1, home_y=2, move_x=1, home_x=2,
                                                     delay_ms=200, timeout_ms=3000, home_delay_ms=0)}]}
        worker = CommWorker(Wrong())
        future = Future()
        entry = (Command(50, 2, 0, a=1, staging=tuple(staging)), future, 0)
        with self.assertRaises(RuntimeError):
            worker._ack_complete(entry, {"result": 0, "message": "accepted"})
        with self.assertRaises(RuntimeError):
            future.result(0.1)
        history = worker.state()["events"]
        self.assertTrue(any("写参数提交 · 气缸 0" in e["message"] and "回读" in e["message"] for e in history))

    def test_shutdown_transmits_jog_stop_before_close(self):
        from backend.comm_worker import CommWorker
        class Fake:
            def __init__(self):
                self.codes = []
            def tick(self, elapsed):
                pass
            def snapshot(self):
                return {"connected": True}
            def command(self, code, *args, **kwargs):
                self.codes.append(code)
                return {"result": 0, "message": "accepted"}
            def renew_jog(self, *args):
                pass
            def close(self):
                self.codes.append("close")
        transport = Fake()
        worker = CommWorker(transport)
        worker.start()
        worker.begin_jog(0, 1, "proof").result(1)
        worker.stop()
        self.assertEqual(transport.codes[-2:], [26, "close"])

    def test_jog_deadman_and_stop_cancel_queued_motion(self):
        from backend.comm_worker import CommWorker
        from backend.mock_plc import MockPlc
        worker = CommWorker(MockPlc(), mode="mock", poll_interval=0.02)
        worker.start()
        try:
            worker.command(20, 1, 0).result(1)
            worker.begin_jog(0, 1, "test-token").result(1)
            time.sleep(0.7)
            self.assertFalse(worker.state()["axes"][0]["running"])
            worker.renew_jog("test-token")
            time.sleep(0.1)
            self.assertFalse(worker.state()["axes"][0]["running"])
        finally:
            worker.stop()

    def test_stops_clear_unsent_normal_commands(self):
        from backend.comm_worker import CommWorker
        from backend.mock_plc import MockPlc
        worker = CommWorker(MockPlc(), mode="mock")
        normal = worker.command(20, 1, 0)
        stop = worker.command(10)
        worker.start()
        try:
            self.assertEqual(stop.result(1)["result"], 0)
            with self.assertRaises(RuntimeError):
                normal.result(1)
        finally:
            worker.stop()


if __name__ == "__main__":
    unittest.main()
