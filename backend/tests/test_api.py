import unittest
from fastapi.testclient import TestClient


class ApiTests(unittest.TestCase):
    def test_simulation_configuration_name_and_point_readback(self):
        state = self.post("/api/connect", {"mode": "mock"}).json()
        session = state["session"]
        def current():
            return self.client.get("/api/state").json()
        epoch = current()["config_epoch"]
        response = self.post("/api/name", {"session": session, "object_type": 1,
                             "object_index": 0, "name": "审查轴A"})
        self.assertTrue(response.json()["ok"])
        self.assertEqual(current()["axes"][0]["name"], "审查轴A")
        # A rename is host metadata only: the PLC configuration epoch does not move.
        self.assertEqual(current()["config_epoch"], epoch)
        response = self.post("/api/config", {"session": session, "object_type": 1,
                             "object_index": 0, "values": {"manual_speed": 12.345}, "epoch": current()["config_epoch"]})
        self.assertEqual(response.json()["result"], 0)
        self.assertEqual(current()["axes"][0]["config"]["manual_speed"], 12.345)
        # Slot 19 is free; teaching claims it for axis 0.
        response = self.post("/api/point", {"session": session, "axis": 0, "point": 19, "position": -12.345, "speed": 10})
        self.assertEqual(response.json()["result"], 0)
        self.assertEqual(current()["points"][19]["owner"], 0)
        point = next(p for p in current()["axes"][0]["points"] if p["index"] == 19)
        self.assertTrue(point["taught"])
        self.assertFalse(point["enabled"])
        response = self.post("/api/config", {"session": session, "object_type": 3,
                             "object_index": 19, "values": {"flags": 3}, "epoch": current()["config_epoch"]})
        self.assertEqual(response.json()["result"], 0)
        point = next(p for p in current()["axes"][0]["points"] if p["index"] == 19)
        self.assertTrue(point["enabled"])
        self.assertEqual(current()["points"][19]["owner"], 0)

    def setUp(self):
        from backend.api import create_app
        self.context = TestClient(create_app(testing=True))
        self.client = self.context.__enter__()
        self.token = self.client.get("/api/meta").json()["csrf_token"]
        self.headers = {"X-CSRF-Token": self.token}

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def test_overlong_name_rejected_as_validation_error(self):
        self.post("/api/connect", {"mode": "mock"})
        session = self.client.get("/api/state").json()["session"]
        response = self.post("/api/name", {"session": session, "object_type": 1,
                             "object_index": 0, "name": "x" * 33})
        self.assertEqual(response.status_code, 422)

    def test_name_requires_session_and_detects_stale_revision(self):
        self.post("/api/connect", {"mode": "mock"})
        state = self.client.get("/api/state").json()
        self.assertEqual(self.post("/api/name", {"session": "old", "object_type": 1, "object_index": 0,
                                                 "name": "A"}).status_code, 409)
        revision = state["names_revision"]
        first = self.post("/api/name", {"session": state["session"], "object_type": 1, "object_index": 0,
                                        "name": "A", "revision": revision})
        self.assertEqual(first.status_code, 200)
        stale = self.post("/api/name", {"session": state["session"], "object_type": 1, "object_index": 0,
                                        "name": "B", "revision": revision})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get("/api/state").json()["axes"][0]["name"], "A")

    def test_rename_sends_no_plc_command(self):
        self.post("/api/connect", {"mode": "mock"})
        app_host = self.context.app.state.host
        calls = []
        original = app_host.worker.command
        app_host.worker.command = lambda *a, **k: calls.append(a) or original(*a, **k)
        session = self.client.get("/api/state").json()["session"]
        self.post("/api/name", {"session": session, "object_type": 3, "object_index": 7, "name": "待机位"})
        self.post("/api/name", {"session": session, "object_type": 2, "object_index": 0, "name": "夹紧气缸"})
        self.assertEqual(calls, [])
        state = self.client.get("/api/state").json()
        self.assertEqual(state["points"][7]["name"], "待机位")
        self.assertEqual(state["cylinders"][0]["name"], "夹紧气缸")
        self.assertEqual(state["axes"][1]["name"], "轴 1")

    def test_delete_point_frees_slot_and_its_alias(self):
        self.post("/api/connect", {"mode": "mock"})
        session = self.client.get("/api/state").json()["session"]
        def state():
            return self.client.get("/api/state").json()
        def delete(index):
            return self.client.request("DELETE", f"/api/point/{index}", json={"session": session}, headers=self.headers)
        self.assertEqual(self.post("/api/point", {"session": session, "axis": 0, "point": 40,
                                                  "position": 1, "speed": 10}).json()["result"], 0)
        self.post("/api/name", {"session": session, "object_type": 3, "object_index": 40, "name": "取料位"})
        self.assertEqual(self.post("/api/config", {"session": session, "object_type": 3, "object_index": 40,
                                                   "values": {"flags": 3}, "epoch": state()["config_epoch"]}).json()["result"], 0)
        rejected = delete(40)
        self.assertEqual(rejected.status_code, 409)
        self.assertIn("启用", rejected.json()["detail"])
        self.assertEqual(self.post("/api/config", {"session": session, "object_type": 3, "object_index": 40,
                                                   "values": {"flags": 2}, "epoch": state()["config_epoch"]}).json()["result"], 0)
        released = delete(40)
        self.assertEqual(released.json()["result"], 0)
        point = state()["points"][40]
        self.assertIsNone(point["owner"])
        self.assertFalse(point["taught"])
        self.assertEqual(point["name"], "点位 40")  # alias removed with the slot
        self.assertEqual(delete(0).status_code, 409)  # P0 standby slot
        self.assertEqual(delete(40).status_code, 409)  # already free
        epoch = state()["config_epoch"]
        claim = self.post("/api/config", {"session": session, "object_type": 3, "object_index": 41,
                                          "values": {"flags": 0}, "epoch": epoch})
        self.assertEqual(claim.status_code, 409)  # free slot must be claimed by teaching first

    def test_command_history_is_specific(self):
        self.post("/api/connect", {"mode": "mock"})
        session = self.client.get("/api/state").json()["session"]
        self.post("/api/command", {"code": 20, "object_type": 1, "object_index": 4, "session": session})
        events = self.client.get("/api/state").json()["events"]
        rejected = next(e for e in events if e.get("category") == "command")
        self.assertIn("使能", rejected["message"])
        self.assertIn("轴 4", rejected["message"])
        self.assertIn("对象未绑定", rejected["message"])
        self.assertEqual(rejected["action"], "核对 PLC 工程绑定常量后重新编译下载")

    def test_default_offline_and_csrf(self):
        self.assertFalse(self.client.get("/api/state").json()["connected"])
        self.assertEqual(self.client.post("/api/connect", json={"mode": "mock"}).status_code, 403)

    def test_simulated_command_and_websocket(self):
        self.assertEqual(self.post("/api/connect", {"mode": "mock"}).status_code, 200)
        with self.client.websocket_connect("/ws") as ws:
            packet = ws.receive_json()
            state = packet["state"]
            self.assertEqual(packet["type"], "snapshot")
            response = self.post("/api/command", {"code": 20, "object_type": 1, "object_index": 0, "session": state["session"]})
            self.assertEqual(response.json()["result"], 0)

    def test_stale_session_and_bad_indices_rejected(self):
        self.post("/api/connect", {"mode": "mock"})
        self.assertEqual(self.post("/api/command", {"code": 20, "session": "old"}).status_code, 409)
        session = self.client.get("/api/state").json()["session"]
        self.assertEqual(self.post("/api/command", {"code": 26, "object_type": 1, "object_index": -1, "session": session}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
