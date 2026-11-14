"""Independent wire-contract expectations, before either runtime exists."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ProtocolContractTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "docs/protocol-v1.json").read_text(encoding="utf-8"))

    def test_windows_are_contiguous_and_sizes_are_exact(self):
        expected = [
            ("command", "holding", 0, 32), ("status", "input", 0, 104), ("io", "input", 104, 20),
            ("axis_live", "input", 124, 256), ("cylinder_live", "input", 380, 162),
            ("axis_config", "input", 542, 256), ("cylinder_config", "input", 798, 432),
            ("points", "input", 1230, 600),
        ]
        windows = self.spec["windows"]
        self.assertEqual([(w["id"], w["area"], w["base"], w["stride"] * w["count"]) for w in windows], expected)
        cursor = {"holding": 0, "input": 0}
        for window in windows:
            self.assertEqual(window["base"], cursor[window["area"]])
            cursor[window["area"]] += window["stride"] * window["count"]
            self.assertEqual(window["end"], cursor[window["area"]] - 1)

    def test_frozen_register_budget_1862_words(self):
        """Names moved to the host: 32 holding + 1830 input, zero name registers."""
        self.assertEqual(self.spec["areas"], {"holding": 32, "input": 1830})
        self.assertEqual(sum(self.spec["areas"].values()), 1862)
        self.assertNotIn("names", {w["id"] for w in self.spec["windows"]})
        input_words = [w["stride"] * w["count"] for w in self.spec["windows"] if w["area"] == "input"]
        self.assertEqual(input_words, [104, 20, 256, 162, 256, 432, 600])

    def test_official_modbus_transport_on_port_1502(self):
        transport = self.spec["transport"]
        self.assertEqual(transport["port"], 1502)
        self.assertEqual(transport["holding_function_read"], 3)
        self.assertEqual(transport["holding_function_write"], [6, 16])
        self.assertEqual(transport["input_function_read"], 4)

    def test_every_word_is_named_once(self):
        for window in self.spec["windows"]:
            occupied = []
            for field in window["fields"]:
                occupied.extend(range(field["offset"], field["offset"] + field["words"]))
            with self.subTest(window=window["id"]):
                self.assertEqual(sorted(occupied), list(range(window["stride"])))

    def test_capacity_and_signature(self):
        self.assertEqual(self.spec["signature"], 0x584A5633)
        self.assertEqual(self.spec["capacities"], {"axes": 16, "cylinders": 54, "points": 120})
        self.assertEqual(self.spec["word_order"], "high_first")

    def test_point_speed_and_enable_are_not_truncated(self):
        points = next(w for w in self.spec["windows"] if w["id"] == "points")
        self.assertEqual(points["fields"], [
            {"id": "position", "offset": 0, "words": 2, "type": "DINT"},
            {"id": "speed", "offset": 2, "words": 2, "type": "UDINT"},
            {"id": "flags", "offset": 4, "words": 1, "type": "WORD"},
        ])
        self.assertEqual(points["count"], 120)
        status = {f["id"]: f["offset"] for f in next(w for w in self.spec["windows"] if w["id"] == "status")["fields"]}
        self.assertEqual(status["axis_summary"] + self.spec["capacities"]["axes"], status["cylinder_summary"])
        self.assertEqual(status["cylinder_summary"] + self.spec["capacities"]["cylinders"], status["first_alarm"])
        self.assertEqual(status["point_pool"], status["snapshot_epoch"] - 1)

    def test_point_free_encoding_does_not_collide_with_axis_15(self):
        flags = self.spec["point_flags"]
        axis_15 = 15 << flags["owner_shift"]
        self.assertNotEqual(flags["free"], axis_15)
        self.assertFalse(flags["free"] & (flags["owner_mask"] << flags["owner_shift"] | 3))

    def test_alarm_catalogue_is_concrete(self):
        codes = [a["code"] for a in self.spec["alarms"]]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(len(a["message"]) >= 6 and a["action"] for a in self.spec["alarms"]))
        plc = (ROOT / "plc/src/03_pou/功能块_轴.st").read_text(encoding="utf-8") +             (ROOT / "plc/src/03_pou/功能块_气缸.st").read_text(encoding="utf-8")
        import re
        emitted = {int(code) for code in re.findall(r"(?:Error|NewFault) := (\d{4});", plc)}
        self.assertEqual(emitted - set(codes), set(), "every PLC alarm code needs a catalogue entry")

    def test_field_masks_are_unique_and_complete(self):
        for kind, count in (("axis", 8), ("cylinder", 3), ("point", 3)):
            masks = self.spec["field_masks"][kind]
            self.assertEqual([f["mask"] for f in masks], [1 << i for i in range(count)])
            self.assertEqual(len({f["id"] for f in masks}), count)

    def test_commands_and_rejection_messages(self):
        codes = [c["code"] for c in self.spec["commands"]]
        self.assertEqual(codes, [1, 2, 3, 4, 9, 10, 11, *range(20, 32), 40, 41, 42, 50, 52, 53])
        self.assertEqual(len(codes), len(set(codes)))
        self.assertFalse(self.spec["commands"][-1]["enabled"])
        errors = self.spec["rejections"]
        self.assertEqual([e["code"] for e in errors], list(range(29)))
        self.assertTrue(all(e["message"] and e["action"] for e in errors))

    def test_snapshot_and_jog_contract(self):
        windows = {w["id"]: w for w in self.spec["windows"]}
        fields = {f["id"]: f for f in windows["command"]["fields"]}
        self.assertEqual(fields["commit"]["offset"], 4)
        self.assertEqual(fields["jog_renew"]["offset"], 12)
        self.assertEqual(fields["staging"]["words"], 16)
        self.assertEqual(self.spec["timing_ms"]["jog_lease"], 1500)
        self.assertEqual(self.spec["timing_ms"]["browser_deadman"], 400)
        for name in ("axis_config", "cylinder_config", "points", "axis_live", "cylinder_live", "io"):
            self.assertEqual(windows[name]["access"], "read")

    def test_generated_artifacts_match_contract(self):
        from tools.check_protocol import render_markdown, render_st
        self.assertEqual((ROOT / "docs/register-map.md").read_text(encoding="utf-8"), render_markdown(self.spec))
        self.assertEqual((ROOT / "plc/src/02_gvl/全局变量_地址表.gvl.st").read_text(encoding="utf-8"), render_st(self.spec))


if __name__ == "__main__":
    unittest.main()
