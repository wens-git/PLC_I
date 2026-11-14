"""Host-owned name store: durability, legacy layout and merge behaviour."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.name_store import NameConflict, NameStore


class NameStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "names.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_names_survive_restart_and_keep_a_backup(self):
        store = NameStore(self.path)
        store.set("mock", "axis", 0, "送料轴")
        store.set("mock", "axis", 1, "压合轴")
        reopened = NameStore(self.path)
        self.assertEqual(reopened.profile("mock")["names"], {"axis:0": "送料轴", "axis:1": "压合轴"})
        backup = json.loads((self.path.parent / "names.json.bak").read_text(encoding="utf-8"))
        self.assertEqual(backup["profiles"]["mock"]["names"], {"axis:0": "送料轴"})

    def test_crash_between_backup_and_replace_recovers_from_backup(self):
        store = NameStore(self.path)
        store.set("mock", "axis", 0, "送料轴")
        store.set("mock", "axis", 0, "新名称")
        # Simulate the old failure window: names.json gone, .bak intact.
        self.path.unlink()
        recovered = NameStore(self.path)
        self.assertEqual(recovered.profile("mock")["names"], {"axis:0": "送料轴"})
        self.assertIn("备份恢复", recovered.error)

    def test_save_never_leaves_names_json_missing(self):
        store = NameStore(self.path)
        store.set("mock", "axis", 0, "A")
        store.set("mock", "axis", 0, "B")
        self.assertTrue(self.path.exists())
        self.assertFalse((self.path.parent / "names.json.tmp").exists())

    def test_corrupt_file_falls_back_to_backup(self):
        store = NameStore(self.path)
        store.set("mock", "axis", 0, "A")
        store.set("mock", "axis", 0, "B")
        self.path.write_text("{broken", encoding="utf-8")
        recovered = NameStore(self.path)
        self.assertEqual(recovered.profile("mock")["names"], {"axis:0": "A"})
        self.assertIn("损坏", recovered.error)

    def test_first_run_has_no_error(self):
        store = NameStore(self.path)
        self.assertEqual(store.profiles, {})
        self.assertEqual(store.error, "")

    def test_legacy_flat_layout_lands_on_the_simulator_profile(self):
        self.path.write_text(json.dumps({"names": {"axis:0": "旧名称"}}, ensure_ascii=False), encoding="utf-8")
        store = NameStore(self.path)
        self.assertEqual(store.profile("mock")["names"], {"axis:0": "旧名称"})

    def test_stale_revision_is_rejected(self):
        store = NameStore(self.path)
        seen = store.profile("mock")["revision"]
        store.set("mock", "axis", 0, "A", revision=seen)
        with self.assertRaises(NameConflict):
            store.set("mock", "axis", 0, "B", revision=seen)
        self.assertEqual(store.profile("mock")["names"]["axis:0"], "A")

    def test_profiles_are_isolated(self):
        store = NameStore(self.path)
        store.set("mock", "axis", 0, "模拟")
        store.set("192.168.6.6:502/1", "axis", 0, "真机")
        self.assertEqual(store.profile("mock")["names"]["axis:0"], "模拟")
        self.assertEqual(store.profile("192.168.6.6:502/1")["names"]["axis:0"], "真机")

    def test_merge_labels_axis_point_copies(self):
        store = NameStore(self.path)
        store.set("mock", "point", 7, "待机位")
        state = {"axes": [{"index": 0, "points": [{"index": 7}, {"index": 8}]}],
                 "cylinders": [], "points": [{"index": 7}, {"index": 8}]}
        store.merge("mock", state)
        self.assertEqual(state["points"][0]["name"], "待机位")
        self.assertEqual(state["axes"][0]["points"][0]["name"], "待机位")
        self.assertEqual(state["axes"][0]["points"][1]["name"], "点位 8")


if __name__ == "__main__":
    unittest.main()
