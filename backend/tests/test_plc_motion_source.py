"""Motion adapter source contracts, not ST execution or compiler evidence."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2] / "plc/src"


def st(path):
    return (ROOT / path).read_text(encoding="utf-8")


class MotionSourceTests(unittest.TestCase):
    def test_axis_wire_state_contract(self):
        text = st("01_types/结构体_轴状态.st")
        for name in ("b在线", "b已使能", "b运动中", "b已回原", "b故障", "b静止",
                     "b正向点动", "b负向点动"):
            self.assertRegex(text, rf"\b{name}\s*:\s*BOOL")
        for name in ("di位置", "di速度", "di目标"):
            self.assertRegex(text, rf"\b{name}\s*:\s*DINT")
        for name in ("w错误码", "w序列", "w运动结果", "w限位"):
            self.assertRegex(text, rf"\b{name}\s*:\s*WORD")
        self.assertRegex(text, r"dw驱动错误\s*:\s*DWORD")

    def test_axis_exact_interface_and_single_mc_owner(self):
        text = st("03_pou/功能块_轴.st")
        for fragment in ("Axis : AXIS_REF_SM3", "State : 结构体_轴状态",
                         "Code : WORD", "Sequence : WORD", "Target : DINT",
                         "Speed : UDINT", "Acceleration : UDINT", "Deceleration : UDINT",
                         "StopDeceleration : UDINT", "HardEstop : BOOL",
                         "PositiveLimit : BOOL", "NegativeLimit : BOOL", "BusOperational : BOOL := TRUE"):
            self.assertIn(fragment, text)
        for fb in ("上电", "读状态", "读位置", "读速度", "运动",
                   "点动", "回原", "停止", "复位", "清零"):
            self.assertEqual(len(re.findall(rf"\bfb{fb}\s*\(", text)), 1, fb)
        self.assertNotIn("ast定位", text)
        self.assertNotIn("[19]", text)

    def test_axis_error_reports_payload_only_when_valid(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("IF fb读轴错.Valid AND NOT fb读轴错.Error THEN", text)
        self.assertIn("dw新驱动错误 := fb读轴错.AxisErrorID;", text)
        self.assertIn("ELSIF fb读轴错.Error THEN", text)

    def test_missing_stop_deceleration_fallback_is_not_overwritten(self):
        text = st("03_pou/功能块_轴.st")
        branch = text[text.index("24, 25, 27:"):text.index("30:")]
        self.assertEqual(branch.count("lr锁定停止减速度 := UDINT_TO_LREAL(StopDeceleration) / 1000.0;"), 1)
        self.assertIn("lr锁定停止减速度 := UDINT_TO_LREAL(Deceleration) / 1000.0;", branch)

    def test_power_does_not_mask_errorstop_before_reset(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("Enable := (NOT b执行复位 AND NOT fb读状态.Errorstop) OR HardEstop", text)
        self.assertIn("State.b在线 := BusOperational AND (OpenLoop OR b反馈有效)", text)

    def test_installed_home_zero_and_units_contract(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("SM3_Basic 4.10.0.0", text)
        self.assertIn("lr回原位置 : LREAL := 0.0", text)
        self.assertIn("lr位置容差 : LREAL := 0.03", text)
        self.assertIn("Mode := FALSE", text)
        self.assertIn("Position := lr回原位置", text)
        self.assertIn("DINT_TO_LREAL(Target) / 1000.0", text)
        self.assertIn("UDINT_TO_LREAL(Speed) / 1000.0", text)
        self.assertIn("LREAL#-2147483648", text)
        self.assertIn("LREAL#2147483647", text)
        self.assertIn("fb读位置.Valid AND NOT fb读位置.Error", text)
        self.assertIn("fb读速度.Valid AND NOT fb读速度.Error", text)

    def test_stop_cancels_before_mc_stop_and_delays_disable(self):
        text = st("03_pou/功能块_轴.st")
        start = text.index("IF i停止阶段 <> 0 THEN")
        call = text.index("fb停止(")
        self.assertLess(start, text.index("b执行运动 := FALSE", start))
        self.assertLess(text.index("b执行运动 := FALSE", start), call)
        self.assertLess(text.index("b正向点动 := FALSE", start), call)
        self.assertIn("i停止阶段 := 3", text)
        self.assertIn("fb停止.Done", text)
        self.assertIn("b待去使能", text)
        self.assertIn("tmr停止", text)
        self.assertIn("PT := T#30s", text)
        self.assertIn("PT := T#180s", text)

    def test_latched_commands_require_explicit_recovery(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("IF NOT b已初始化 THEN", text)
        self.assertIn("b新命令 := FALSE", text)
        self.assertIn("Sequence <> w上次序列", text)
        self.assertIn("IF HardEstop THEN", text)
        self.assertIn("b请求上电 := FALSE", text)
        self.assertIn("b需恢复 := TRUE", text)
        self.assertIn("NOT b需恢复", text)
        self.assertIn("PositiveLimit AND", text)
        self.assertIn("NegativeLimit AND", text)

    def test_completion_checks_feedback_and_fb_reset_cycle(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("b待验证", text)
        self.assertIn("ABS(fb读位置.Position - lr锁定目标)", text)
        self.assertIn("State.w运动结果 := 2", text)
        self.assertIn("State.w运动结果 := 4", text)
        self.assertIn("b释放周期", text)
        self.assertIn("fb运动.CommandAborted", text)
        self.assertIn("fb回原.CommandAborted", text)

    def test_cylinder_real_sensor_filters_and_target_cancel(self):
        text = st("03_pou/功能块_气缸.st")
        self.assertIn("HasWorkSensor AND SensorWork", text)
        self.assertIn("HasOriginSensor AND SensorOrigin", text)
        self.assertIn("SensorWork AND SensorOrigin", text)
        self.assertIn("Code = 42", text)
        cancel = text[text.index("IF b取消 THEN"):]
        self.assertIn("i目标侧 := 0", cancel)
        self.assertIn("WorkOutput := FALSE", cancel)
        self.assertIn("OriginOutput := FALSE", cancel)
        self.assertIn("DelayMs < TimeoutMs", text)
        self.assertIn("HomeDelayMs < TimeoutMs", text)
        self.assertIn("TimeoutMs > 0", text)
        self.assertIn("ValveType <= 3", text)
        self.assertNotIn("b动点屏蔽", text)

    def test_cylinder_completion_does_not_deenergize_latched_valve(self):
        text = st("03_pou/功能块_气缸.st")
        self.assertIn("WorkOutput := i目标侧 = 1", text)
        self.assertIn("OriginOutput := (i目标侧 = 2) AND ((ValveType = 1) OR (ValveType = 3))", text)
        self.assertIn("IF (ValveType = 3) AND (i目标侧 = 2) THEN OriginOutput := FALSE", text)
        self.assertIn("tmr运动.Q", text)
        self.assertIn("Token <> udi上次请求", text)
        self.assertIn("Fault := TRUE", text)

    def test_reset_precedes_power_and_cannot_be_cancelled_by_old_errorstop(self):
        text = st("03_pou/功能块_轴.st")
        self.assertLess(text.index("fb复位(Axis"), text.index("fb上电(Axis"))
        self.assertIn("w新故障 := 0;\n            b执行复位 := TRUE", text)
        self.assertIn("tmr复位(IN := b执行复位", text)
        self.assertIn("tmr复位.Q", text)
        self.assertIn("Enable := (NOT b执行复位 AND NOT fb读状态.Errorstop) OR HardEstop", text)
        self.assertIn("(Code = 21) OR (Code = 26)", text)

    def test_home_requires_stop_dynamics_and_cylinder_switch_resets_timeout(self):
        axis = st("03_pou/功能块_轴.st")
        branch = axis[axis.index("22:"):axis.index("24, 25, 27:")]
        self.assertIn("StopDeceleration > 0", branch)
        self.assertIn("lr锁定停止减速度 :=", branch)
        cylinder = st("03_pou/功能块_气缸.st")
        self.assertIn("IF b新请求 OR b取消 THEN", cylinder)
        self.assertIn("tmr运动(IN := FALSE", cylinder)

    def test_unexpected_power_loss_requires_recovery(self):
        text = st("03_pou/功能块_轴.st")
        self.assertIn("b请求上电 AND b上电过 AND NOT fb上电.Status", text)
        self.assertIn("b上电过 := fb上电.Status", text)
        self.assertIn("(w新故障 = 1105)", text)

    def test_reset_publishes_sequence_and_completion(self):
        text = st("03_pou/功能块_轴.st")
        branch = text[text.index("ELSIF (Code = 23)"):text.index("ELSIF b可接收")]
        self.assertEqual(branch.count("State.w序列 := Sequence"), 2)
        self.assertIn("State.w运动结果 := 1", branch)
        self.assertIn("State.w运动结果 := 2", branch)
        done = text[text.index("IF b执行复位 AND fb复位.Done"):]
        done = done[:done.index("END_IF;")]
        self.assertIn("State.w运动结果 := 2", done)


if __name__ == "__main__":
    unittest.main()
