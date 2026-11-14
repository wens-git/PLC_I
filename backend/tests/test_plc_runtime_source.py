"""IEC ST source contracts only, not compiler or physical motion evidence."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2] / "plc/src"


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class RuntimeSourceTests(unittest.TestCase):
    def test_runtime_is_volatile_and_requires_explicit_consumers(self):
        text = source("01_types/结构体_运行时.st")
        for field in ("ast轴", "aw轴命令", "aw轴序列", "adi轴目标", "audi轴速度",
                      "audi轴加速度", "audi轴减速度", "audi轴停止减速度"):
            self.assertRegex(text, rf"\b{field}\s*:\s*ARRAY\[0\.\.15\]")
        self.assertIn("b待复位 : BOOL := TRUE", text)
        self.assertIn("w轴消费掩码 : WORD", text)
        self.assertIn("b运行 : BOOL", text)
        self.assertIn("b暂停 : BOOL", text)
        self.assertNotIn("RETAIN", text)

    def test_no_safety_commissioning_gate_remains_in_the_permit_layer(self):
        text = source("03_pou/函数_动作许可.st")
        self.assertNotIn("b需安全", text)
        self.assertNotIn("b安全就绪", text)
        self.assertNotIn("安全已验收", text)
        self.assertNotIn("NOT 全局变量_保持区.Store.b已确认", text)
        self.assertNotIn("NOT Runtime.b待复位", text)
        self.assertIn("(Code = 2) OR (Code = 3) OR (Code = 4)", text)

    def test_stop_bypasses_online_safety_faults_and_integration_but_needs_binding(self):
        text = source("03_pou/函数_动作许可.st")
        self.assertLess(text.index("IF b是停止 THEN"), text.index("IF NOT HmiOnline THEN"))
        stop = text[text.index("IF b是停止 THEN"):text.index("IF NOT HmiOnline THEN")]
        self.assertIn("b对象已绑定", stop)
        self.assertNotIn("b硬件已接入", stop)
        self.assertIn("RETURN", stop)

    def test_dispatch_and_publication_share_the_only_permission_function(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("Runtime : 结构体_运行时", text)
        self.assertIn("w应答结果 := 函数_动作许可(", text)
        self.assertIn("w许可结果 := 函数_动作许可(", text)
        self.assertIn("fb配置(Execute := FALSE", text)
        self.assertIn("fb配置(Execute := TRUE", text)
        self.assertIn("Store := 全局变量_保持区.Store", text)

    def test_system_word_publishes_running_and_paused_from_runtime(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("IF Runtime.b运行 THEN w系统字 := w系统字 OR 4; END_IF;", text)
        self.assertIn("IF Runtime.b暂停 THEN w系统字 := w系统字 OR 1024; END_IF;", text)

    def test_relative_target_widens_before_addition_and_normalizes(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("DINT_TO_LINT(Runtime.ast轴[ui轴号].di位置) + DINT_TO_LINT(di目标)", text)
        self.assertIn("li宽目标 < LINT#-2147483648", text)
        self.assertIn("li宽目标 > LINT#2147483647", text)
        self.assertIn("Runtime.aw轴命令[ui轴号] := 27", text)
        self.assertIn("di目标 < di负限位", text)
        self.assertIn("di目标 > di正限位", text)

    def test_motion_parameters_are_latched_only_on_accepted_dispatch(self):
        text = source("03_pou/功能块_服务端.st")
        for field in ("adi轴目标", "audi轴速度", "audi轴加速度", "audi轴减速度"):
            self.assertIn(f"Runtime.{field}[ui轴号] :=", text)
        self.assertIn("IF w应答结果 = 0 THEN", text)
        self.assertIn("Runtime.aw轴命令[i循环] := 0", text)
        self.assertIn("全局变量_保持区.Store.aw点位[i点位索引, 4] AND 3", text)

    def test_reset_waits_for_axis_completion_without_enabling(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("ui复位阶段", text)
        self.assertIn("Runtime.ast轴[i循环].w序列 = w复位序列", text)
        self.assertIn("Runtime.ast轴[i循环].w运动结果 = 2", text)
        self.assertIn("Runtime.b待复位 := FALSE", text)
        reset = text[text.index("CASE ui复位阶段 OF"):text.index("END_CASE;", text.index("CASE ui复位阶段 OF"))]
        self.assertNotRegex(reset, r"aw轴命令\[.*?\] := (20|22|24|25|27);")
        self.assertIn("tmr复位", text)

    def test_lease_controls_real_stop_and_not_just_exported_intention(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("StartJog := b起点动脉冲", text)
        self.assertIn("StopJog := b停点动脉冲", text)
        self.assertIn("IF fb看门狗.CancelJog THEN", text)
        self.assertIn("Runtime.aw轴命令[ui点动索引] := 26", text)
        self.assertIn("fb看门狗.JogActive OR b起点动脉冲", text)

    def test_complete_publication_uses_real_state_and_retained_records(self):
        text = source("03_pou/功能块_服务端.st")
        for record in ("aw轴配置[i循环, i子循环]", "aw气缸配置[i循环, i子循环]",
                       "aw点位[i循环, i子循环]"):
            self.assertIn("全局变量_保持区.Store." + record, text)
        self.assertNotIn("Names", text)
        for field in ("di位置", "di速度", "di目标", "dw驱动错误", "w序列", "w运动结果"):
            self.assertIn("Runtime.ast轴[i循环]." + field, text)
        self.assertIn("Runtime.aw输入[i循环]", text)
        self.assertIn("Runtime.aw输出[i循环]", text)
        self.assertEqual(text.count("w快照纪元 := w快照纪元 + 1"), 2)
        self.assertNotRegex(text, r"\.b在线\s*:=\s*TRUE")

    def test_fault_reset_and_safe_commands_are_not_lost_to_stop_overrides(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("Runtime.ast轴[i循环].b故障 AND (Runtime.ast轴[i循环].di速度 = 0)", text)
        self.assertIn("IF Runtime.aw轴命令[i循环] <> 21 THEN", text)
        self.assertIn("b安全停止 AND Runtime.ast轴[i循环].b运动中", text)
        self.assertIn("ui复位阶段 := 4", text)
        self.assertIn("4: ui复位阶段 := 0", text)

    def test_pending_consumer_and_cancel_scan_cannot_accept_another_action(self):
        text = source("03_pou/函数_动作许可.st")
        self.assertIn("Runtime.aw轴命令[ui轴号] <> 0", text)
        self.assertIn("(Code <> 21)", text)
        self.assertIn("CASE Code OF", text)

    def test_home_and_clear_position_validate_target_soft_limits(self):
        text = source("03_pou/功能块_服务端.st")
        self.assertIn("(st请求[3] = 22) OR (st请求[3] = 30) OR (st请求[3] = 27)", text)

    def test_adapter_release_and_reset_busy_are_visible_to_permission(self):
        permit = source("03_pou/函数_动作许可.st")
        axis = source("03_pou/功能块_轴.st")
        self.assertIn("NOT Runtime.ast轴[ui轴号].b可下发", permit)
        self.assertIn("State.b可下发 := NOT b释放周期", axis)
        ready = axis[axis.index("State.b可下发 :="):]
        for token in ("NOT b执行复位", "NOT fb复位.Busy", "NOT fb复位.Done",
                      "NOT b待验证", "NOT fb运动.Done", "NOT fb停止.Done"):
            self.assertIn(token, ready)

    def test_zero_requires_power_and_fault_reset_is_retryable(self):
        permit = source("03_pou/函数_动作许可.st")
        enabled = permit[permit.index("IF ((Code = 22)"):permit.index("AND NOT Runtime.ast轴[ui轴号].b已使能")]
        self.assertIn("(Code = 30)", enabled)
        # 清故障必须能在报警态反复重试，不能被残留的运动标志挡住。
        self.assertNotIn("IF (Code = 23) AND Runtime.ast轴[ui轴号].b运动中", permit)


if __name__ == "__main__":
    unittest.main()