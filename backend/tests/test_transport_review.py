"""Independent transport regressions with a deterministic register peer, not hardware."""
import socket
import struct
import threading
import unittest
from unittest.mock import Mock, patch

from backend.plc_transport import PlcTransport
from backend.xj_protocol import (AXES, POINTS, STATUS_OFFSET, Command, WINDOWS, address,
                                 record_encode)


class RegisterPeer:
    """Holding and Input are separate zero-based areas (protocol 1.2)."""

    def __init__(self):
        self.holding = [0] * WINDOWS["command"]["stride"]
        self.input = [0] * (WINDOWS["points"]["base"] + WINDOWS["points"]["stride"] * WINDOWS["points"]["count"])
        self.calls = []
        self.closed = False
        self.hook = None
        status = [0] * WINDOWS["status"]["stride"]
        status[:8] = [0x584A, 0x5633, 1, 7, 0, 0x100, 3, 3]
        status[STATUS_OFFSET["capacity"]] = 0x3610
        status[STATUS_OFFSET["axis_bound"]] = 7
        status[STATUS_OFFSET["axis_online"]] = 7
        status[STATUS_OFFSET["point_pool"]] = POINTS
        status[STATUS_OFFSET["snapshot_epoch"]] = 2
        self.put("status", status)
        axis = record_encode("axis_config", dict(positive_limit=100, negative_limit=-100,
                             manual_speed=1, auto_speed=2, acceleration=3, deceleration=3,
                             estop_deceleration=5, flags=1))
        self.put("axis_config", axis * AXES)
        self.put("cylinder_config", [0, 65535, 65535, 65535, 65535, 200, 3000, 0] * 54)
        self.put("points", [0, 0, 0, 1000, 0x40] * POINTS)

    @property
    def words(self):
        return self.input

    def put(self, name, values):
        base = address(name)
        area = self.holding if WINDOWS[name]["area"] == "holding" else self.input
        area[base:base + len(values)] = values

    def connect(self):
        self.closed = False

    def close(self):
        self.closed = True

    def _read(self, area, kind, base, count):
        self.calls.append((kind, base, count))
        result = area[base:base + count]
        if self.hook:
            self.hook(base, count)
        return result

    def read_holding(self, base, count):
        return self._read(self.holding, "read_holding", base, count)

    def read_input(self, base, count):
        return self._read(self.input, "read", base, count)

    def write_holding(self, base, values):
        self.calls.append(("write", base, tuple(values)))
        self.holding[base:base + len(values)] = values

    def write_single(self, base, value):
        self.calls.append(("single", base, value))
        self.holding[base] = value


class TransportReviewTests(unittest.TestCase):
    def setUp(self):
        self.transport = PlcTransport("127.0.0.1")
        self.peer = RegisterPeer()
        self.transport.client = self.peer

    def tearDown(self):
        self.transport.close()

    def test_ack_rejects_publication_changed_during_status_read(self):
        def mutate(base, count):
            if base == address("status") and count == WINDOWS["status"]["stride"]:
                self.peer.words[address("status", "snapshot_epoch")] += 2
        self.peer.hook = mutate
        with self.assertRaises(RuntimeError):
            self.transport.ack(Command(20, 1, 0, sequence=7), 2)

    def test_submit_never_writes_after_torn_baseline(self):
        self.peer.words[address("status", "snapshot_epoch")] = 3
        with self.assertRaises(RuntimeError):
            self.transport.submit(Command(20, 1, 0))
        self.assertTrue(all(call[0].startswith("read") for call in self.peer.calls))

    def test_transient_publication_is_retried_without_writes(self):
        self.peer.words[address("status", "snapshot_epoch")] = 3
        def complete(base, count):
            if base == address("status", "snapshot_epoch"):
                self.peer.words[base] = 4
        self.peer.hook = complete
        self.assertEqual(self.transport.ack(Command(20, 1, 0, sequence=7), 2)["result"], 0)
        self.assertTrue(all(call[0].startswith("read") for call in self.peer.calls))

    def test_snapshot_interrupts_between_chunks_but_not_submit(self):
        self.transport.read_interrupt = lambda: any(call[1] == address("axis_live") for call in self.peer.calls)
        with self.assertRaises(RuntimeError) as error:
            self.transport.snapshot()
        self.assertEqual(type(error.exception).__name__, "PollInterrupted")
        self.assertFalse(any(call[1] == address("axis_live") + 125 for call in self.peer.calls))
        self.transport.read_interrupt = lambda: True
        self.transport.submit(Command(20, 1, 0, sequence=8))
        self.assertEqual(self.peer.calls[-1], ("single", address("command", "commit"), 8))

    def test_permanent_publication_is_bounded_and_typed(self):
        self.peer.words[address("status", "snapshot_epoch")] = 3
        with self.assertRaises(RuntimeError) as error:
            self.transport.snapshot()
        self.assertEqual(type(error.exception).__name__, "SnapshotUnavailable")
        self.assertLessEqual(len(self.peer.calls), 3)

    def test_ack_requires_identity_epoch_and_valid_protocol(self):
        cmd = Command(20, 1, 0, sequence=7)
        self.assertIsNone(self.transport.ack(cmd, 3))
        self.assertIsNone(self.transport.ack(Command(20, 1, 1, sequence=7), 2))
        self.assertIsNone(self.transport.ack(Command(20, 1, 0, sequence=8), 2))
        self.assertEqual(self.transport.ack(cmd, 2)["result"], 0)
        self.peer.words[address("status", "signature")] = 0
        with self.assertRaises((ValueError, ConnectionError)):
            self.transport.ack(cmd, 2)

    def test_live_batch_deadline_includes_all_requests(self):
        clock = [0.0]
        def delay(base, count):
            if address("io") <= base < address("cylinder_live") + 162:
                clock[0] += 0.25
        self.peer.hook = delay
        with patch("backend.plc_transport.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(TimeoutError):
                self.transport.snapshot()

    def test_invalid_point_flags_do_not_enter_cache(self):
        slot = address("points", "flags", index=20)
        for invalid in (0x40 | 4, 0x40 | 1, 0x80, 1, 0x3C | 1):
            with self.subTest(invalid=hex(invalid)):
                self.transport.cached_config = self.transport.cached_epoch = None
                self.peer.input[slot] = invalid
                with self.assertRaises(ValueError):
                    self.transport.snapshot()
                self.assertIsNone(self.transport.cached_config)

    def test_axis_15_point_is_not_decoded_as_free(self):
        self.peer.input[address("points", "flags", index=20)] = 15 << 2
        state = self.transport.snapshot()
        self.assertEqual(state["points"][20]["owner"], 15)
        self.assertIsNone(state["points"][21]["owner"])

    def test_handshake_writes_protocol_12_signature(self):
        self.peer.input[address("status", "system")] = 1
        self.transport.connect()
        self.assertEqual(self.peer.holding[:2], [0x584A, 0x5633])

    def test_sequence_is_seeded_from_holding_seq_not_published_ack(self):
        """After a PLC restart the ACK SEQ is 0 while Holding word 4 still holds 1;
        the PLC treats 1 as its baseline, so the host must not pick SEQ 1 next."""
        self.peer.input[address("status", "system")] = 1
        self.peer.input[address("status", "ack_seq")] = 0
        self.peer.holding[address("command", "commit")] = 1
        seed = self.transport.connect()
        self.assertEqual(seed, 1)
        self.assertNotEqual(seed % 65535 + 1, 1)

    def test_reserved_configuration_word_rejected_before_caching(self):
        self.peer.words[address("axis_config") + 15] = 1
        with self.assertRaises(ValueError):
            self.transport.snapshot()
        self.assertIsNone(self.transport.cached_config)

    def test_io_tail_bits_and_reserved_words_are_rejected(self):
        for offset in (2, 18):
            with self.subTest(offset=offset):
                self.peer.put("io", [0] * 20)
                self.peer.words[address("io") + offset] = 1
                with self.assertRaises(ValueError):
                    self.transport.snapshot()

    def test_config_epoch_change_does_not_publish_or_cache(self):
        def change(base, count):
            if base == address("points"):
                self.peer.words[address("status", "config_epoch")] += 1
        self.peer.hook = change
        with self.assertRaises(RuntimeError):
            self.transport.snapshot()
        self.assertIsNone(self.transport.cached_config)

    def test_binding_change_invalidates_config_even_when_config_epoch_matches(self):
        self.transport.snapshot()
        self.peer.words[address("status", "binding_epoch")] += 1
        self.peer.words[address("axis_config") + 15] = 1
        with self.assertRaises(ValueError):
            self.transport.snapshot()

    def test_config_deadline_includes_final_epoch_read(self):
        clock = [0.0]
        reads = [0]
        def delay(base, count):
            if base == address("status", "config_epoch"):
                reads[0] += 1
                if reads[0] == 2:
                    clock[0] += 1.1
        self.peer.hook = delay
        with patch("backend.plc_transport.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(TimeoutError):
                self.transport.snapshot()
        self.assertIsNone(self.transport.cached_config)

    def test_live_state_is_refreshed_after_config_batch(self):
        def change(base, count):
            if base == address("points"):
                self.peer.words[address("axis_live")] = 0
                self.peer.words[address("axis_live") + 1] = 1234
                self.peer.words[address("status", "snapshot_epoch")] += 2
        self.peer.hook = change
        state = self.transport.snapshot()
        self.assertEqual(state["axes"][0]["position"], 1.234)

    def test_config_cache_is_immutable_and_public_state_is_detached(self):
        state = self.transport.snapshot()
        with self.assertRaises(TypeError):
            self.transport.cached_config["points"][0] = 88
        with self.assertRaises(TypeError):
            self.transport.cached_config["points"] = ()
        state["axes"][0]["config"]["manual_speed"] = 999
        self.assertEqual(self.transport.snapshot()["axes"][0]["config"]["manual_speed"], 1)

    def test_failed_connect_closes_socket_and_discards_cache(self):
        self.transport.snapshot()
        def fail(base, count):
            raise ConnectionError("injected read failure")
        self.peer.hook = fail
        with self.assertRaises(ConnectionError):
            self.transport.connect()
        self.assertTrue(self.peer.closed)
        self.assertIsNone(self.transport.cached_config)

    def test_fc03_chunks_and_commit_write_order(self):
        self.transport.read("points")
        reads = [call for call in self.peer.calls if call[0] == "read"]
        self.assertEqual(sum(call[2] for call in reads), WINDOWS["points"]["stride"] * POINTS)
        self.assertTrue(all(1 <= call[2] <= 125 for call in reads))
        self.peer.calls.clear()
        self.transport.submit(Command(20, 1, 0, sequence=8))
        writes = [call for call in self.peer.calls if call[0] != "read"]
        self.assertEqual([call[1] for call in writes],
                         [address("command", "object"), address("command", "staging"),
                          address("command", "code"), address("command", "commit")])
        self.assertEqual(writes[-1], ("single", address("command", "commit"), 8))


class ModbusResponseReviewTests(unittest.TestCase):
    def setUp(self):
        from backend.modbus_client import ModbusTcpClient
        self.client = ModbusTcpClient("127.0.0.1")
        self.client.client = Mock()

    @staticmethod
    def response(function, **fields):
        return Mock(function_code=function, dev_id=1, isError=lambda: False, **fields)

    def test_single_write_rejects_wrong_echo(self):
        for address_value, registers in ((5, [8]), (4, [9]), (4, [])):
            with self.subTest(address=address_value, registers=registers):
                self.client.client.write_register.return_value = self.response(6, address=address_value, registers=registers)
                with self.assertRaises(ConnectionError):
                    self.client.write_single(4, 8)

    def test_multiple_write_rejects_wrong_address_or_count(self):
        for address_value, count in ((17, 2), (16, 1)):
            with self.subTest(address=address_value, count=count):
                self.client.client.write_registers.return_value = self.response(16, address=address_value, count=count)
                with self.assertRaises(ConnectionError):
                    self.client.write_holding(16, [1, 2])

    def test_read_rejects_wrong_function_or_unit(self):
        for function, unit in ((4, 1), (3, 2)):
            response = self.response(function, registers=[1])
            response.dev_id = unit
            self.client.client.read_holding_registers.return_value = response
            with self.subTest(function=function, unit=unit), self.assertRaises(ConnectionError):
                self.client.read_holding(96, 1)

    def test_valid_response_shapes(self):
        self.client.client.read_holding_registers.return_value = self.response(3, registers=[1])
        self.client.client.write_register.return_value = self.response(6, address=4, registers=[8])
        self.client.client.write_registers.return_value = self.response(16, address=16, count=2)
        self.assertEqual(self.client.read_holding(96, 1), [1])
        self.client.write_single(4, 8)
        self.client.write_holding(16, [1, 2])


class LoopbackFramingReviewTests(unittest.TestCase):
    def exchange(self, operation, response_pdu):
        from backend.modbus_client import ModbusTcpClient
        requests = []
        errors = []
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)

        def serve():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(0.5)
                    data = b""
                    while len(data) < 12:
                        part = connection.recv(12 - len(data))
                        if not part:
                            raise AssertionError("Request was truncated")
                        data += part
                    requests.append(data)
                    if response_pdu is not None:
                        frame = data[:2] + struct.pack(">HHB", 0, len(response_pdu) + 1, data[6]) + response_pdu
                        for byte in frame:
                            connection.sendall(bytes([byte]))
                    try:
                        extra = connection.recv(1024)
                        if extra:
                            requests.append(extra)
                    except socket.timeout:
                        pass
            except Exception as exc:
                errors.append(exc)
            finally:
                listener.close()

        thread = threading.Thread(target=serve)
        thread.start()
        client = ModbusTcpClient("127.0.0.1", listener.getsockname()[1], timeout=0.1)
        try:
            client.connect()
            operation(client)
        finally:
            client.close()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(requests), 1, "A write/read was unexpectedly retried")
        self.assertEqual(struct.unpack(">H", requests[0][4:6])[0], 6)
        return requests[0]

    def test_fragmented_fc03_frame_is_reassembled(self):
        snapshot_address = address("status", "snapshot_epoch")
        request = self.exchange(lambda client: self.assertEqual(client.read_holding(snapshot_address, 2), [0x584A, 0x5633]),
                                bytes.fromhex("03 04 58 4a 56 33"))
        self.assertEqual(request[6:], bytes([1, 3, 0, snapshot_address, 0, 2]))

    def test_wrong_fc06_echo_is_rejected_over_tcp(self):
        def operation(client):
            with self.assertRaises(ConnectionError):
                client.write_single(4, 8)
        self.exchange(operation, bytes.fromhex("06 00 04 00 09"))

    def test_lost_commit_response_never_replays_write(self):
        from pymodbus.exceptions import ModbusException
        def operation(client):
            with self.assertRaises((ModbusException, ConnectionError)):
                client.write_single(4, 8)
        request = self.exchange(operation, None)
        self.assertEqual(request[6:], bytes.fromhex("01 06 00 04 00 08"))


if __name__ == "__main__":
    unittest.main()
