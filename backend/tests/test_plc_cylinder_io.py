"""Source contracts for the cylinder IO layer and safety fixes. No compiler."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2] / "plc/src"


def st(path):
    return (ROOT / path).read_text(encoding="utf-8")


class CylinderIoLayerTests(unittest.TestCase):
    def test_physical_images_and_capacities_are_declared(self):
        images = st("hardware/全局变量_气缸IO映像.gvl.st")
        self.assertIn("aw气缸输入映像 : ARRAY[0..6] OF WORD", images)
        self.assertIn("aw气缸输出映像 : ARRAY[0..3] OF WORD", images)
        self.assertIn("ui气缸输入点数 : UINT := 112", images)
        self.assertIn("ui气缸输出点数 : UINT := 56", images)
        self.assertIn("b气缸输入模块在线", images)
        self.assertIn("b气缸输出模块在线", images)

    def test_input_map_reads_image_and_derives_flags(self):
        text = st("hardware/程序_气缸输入映射.st")
        self.assertIn("aw气缸输入映像[ui地址 / 16] AND SHL(WORD#1, ui地址 MOD 16)", text)
        self.assertIn("ab气缸映射有效[i] := 气缸_配置有效", text)
        self.assertIn("IF 全局变量_运行配置.b气缸IO模块诊断已接入 THEN", text)
        self.assertIn("b模块就绪 := b气缸输入模块在线 AND b气缸输出模块在线", text)
        self.assertIn("b模块就绪 := 全局变量_运行配置.b气缸IO已接入", text)
        self.assertIn("ab气缸模块就绪[i] := b模块就绪", text)
        self.assertNotIn("ab气缸动点输出[i] :=", text)

    def test_output_map_drives_image_only_for_valid_bound(self):
        text = st("hardware/程序_气缸输出映射.st")
        self.assertIn("FOR i := 0 TO 3 DO", text)
        self.assertIn("aw气缸输出映像[i] := 0", text)
        self.assertIn("AND ab气缸映射有效[i] AND ab气缸模块就绪[i]", text)
        self.assertIn("aw气缸输出映像[ui地址 / 16] :=", text)

    def test_main_cycle_orders_input_and_output_maps(self):
        prg = st("entry/程序_主循环.st")
        self.assertLess(prg.index("程序_气缸输入映射();"), prg.index("fb气缸调度(StopAll :="))
        self.assertLess(prg.index("fb气缸调度(StopAll :="), prg.index("程序_气缸输出映射();"))

    def test_direct_wiring_lives_in_the_two_mapping_programs(self):
        inputs = st("hardware/程序_气缸输入映射.st")
        self.assertIn("ab气缸动点传感器[0] := bCY00_动点传感器;", inputs)
        self.assertIn("ab气缸原点传感器[0] := bCY00_原点传感器;", inputs)
        self.assertIn("ab气缸动点传感器[1] := bCY01_动点传感器;", inputs)
        outputs = st("hardware/程序_气缸输出映射.st")
        self.assertIn("bCY00_动点阀 := ab气缸动点输出[0];", outputs)
        self.assertIn("bCY01_原点阀 := ab气缸原点输出[1];", outputs)

    def test_removed_manual_wiring_flags_are_not_used(self):
        for path in ("application/函数_动作许可.st", "communication/功能块_服务端.st",
                     "cylinder/功能块_气缸调度.st"):
            self.assertNotIn("ab气缸映射已核验", st(path))


class CylinderSafetyFixTests(unittest.TestCase):
    def test_clear_fault_does_not_auto_enable_axis(self):
        axis = st("motion/功能块_轴.st")
        branch = axis[axis.index("ELSIF (Code = 23)"):axis.index("ELSIF b可接收")]
        self.assertNotIn("b请求上电 := TRUE", branch)
        self.assertIn("不自动使能", branch)
        done = axis.split("IF b执行复位 AND fb复位.Done THEN", 1)[1].split("END_IF;", 1)[0]
        self.assertNotIn("b请求上电 := TRUE", done)
        self.assertIn("b请求上电 := FALSE", done)

    def test_vacuum_timeout_keeps_adsorption_outputs(self):
        driver = st("cylinder/功能块_气缸.st")
        timeout = driver[driver.index("IF tmr运动.Q THEN"):]
        self.assertIn("IF (ValveType <> 2) AND (ValveType <> 3) THEN", timeout)
        self.assertIn("WorkOutput := FALSE; OriginOutput := FALSE;", timeout)
        self.assertIn("ELSIF ValveType = 3 THEN\n        OriginOutput := FALSE", timeout)

    def test_fault_cancel_keeps_vacuum_but_drops_ordinary_valves(self):
        driver = st("cylinder/功能块_气缸.st")
        block = driver[driver.index("IF b取消 THEN"):driver.index("ELSIF b新请求 AND ((Code = 40)")]
        self.assertIn("ELSIF Fault THEN", block)
        self.assertIn("IF (ValveType <> 2) AND (ValveType <> 3) THEN", block)

    def test_motion_requires_hard_limits_or_enabled_soft_limits(self):
        permit = st("application/函数_动作许可.st")
        self.assertIn("NOT 全局变量_运行配置.b硬限位已接线", permit)
        self.assertIn("Store.aw轴配置[ui轴号, 14] AND WORD#16#0001", permit)
        config = st("hardware/全局变量_运行配置.gvl.st")
        self.assertIn("b硬限位已接线 : BOOL := FALSE", config)

    def test_cross_cylinder_input_duplicates_are_rejected(self):
        text = st("cylinder/气缸_配置有效.st")
        for bounds in ("1 TO 2", "3 TO 4"):
            self.assertIn(f"FOR j := {bounds} DO", text)
            self.assertIn(f"FOR k := {bounds} DO", text)
        self.assertNotIn("FOR j := 1 TO 4 DO", text)
        self.assertIn("WORD_TO_UINT(Store.aw气缸配置[缸号, i]) >= ui气缸输出点数", text)
        self.assertIn("WORD_TO_UINT(Store.aw气缸配置[缸号, i]) >= ui气缸输入点数", text)

    def test_binding_epoch_tracks_binding_table(self):
        server = st("communication/功能块_状态发布.st")
        self.assertIn("w当前绑定纪元", server)
        self.assertIn("(lw上次绑定气缸 <> lw已绑定气缸) OR (w上次绑定轴 <> w已绑定轴)", server)
        self.assertIn("XJV1_STATUS_BINDING_EPOCH_OFFSET] := w当前绑定纪元", server)


if __name__ == "__main__":
    unittest.main()
