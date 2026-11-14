"""Cylinder command-chain source contracts, not IEC execution evidence."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2] / "plc/src"


def st(path):
    return (ROOT / path).read_text(encoding="utf-8")


class CylinderChainTests(unittest.TestCase):
    def test_runtime_declares_cylinder_routing_and_state(self):
        runtime = st("01_types/结构体_运行时.st")
        for fragment in ("ast气缸 : ARRAY[0..53] OF 结构体_气缸状态",
                         "aw气缸命令 : ARRAY[0..53] OF WORD",
                         "aw气缸序列 : ARRAY[0..53] OF WORD"):
            self.assertIn(fragment, runtime)
        state = st("01_types/结构体_气缸状态.st")
        for name in ("b在动点", "b在原点", "b运动中", "b故障"):
            self.assertRegex(state, rf"\b{name}\s*:\s*BOOL")
        self.assertRegex(state, r"\bw错误码\s*:\s*WORD")

    def test_stop_codes_bypass_integration_but_reject_unbound(self):
        permit = st("03_pou/函数_动作许可.st")
        stop = permit[permit.index("IF b是停止 THEN"):permit.index("IF NOT HmiOnline THEN")]
        self.assertIn("函数_动作许可 := 4", stop)
        self.assertNotIn("b硬件已接入", stop)

    def test_cylinder_binding_comes_from_engineering_constant(self):
        permit = st("03_pou/函数_动作许可.st")
        self.assertIn("(lw已绑定气缸 AND SHL(LWORD#1, ui对象索引)) <> 0", permit)

    def test_ordinary_cylinder_commands_stay_explicitly_gated(self):
        permit = st("03_pou/函数_动作许可.st")
        gate = permit.index("IF w类别 = 2 THEN\n    IF Resetting")
        self.assertLess(gate, permit.index("Runtime.aw轴命令[ui轴号]"))
        for check in ("ab气缸模块就绪[ui对象索引]", "IF NOT b硬件已接入", "IF Runtime.b暂停", "气缸_配置有效"):
            self.assertIn(check, permit[gate:permit.index("Runtime.aw轴命令[ui轴号]")])

    def test_server_routes_stop_and_clears_cylinder_codes_each_scan(self):
        server = st("03_pou/功能块_服务端.st")
        self.assertIn("FOR i循环 := 0 TO 53 DO Runtime.aw气缸命令[i循环] := 0; END_FOR;", server)
        branch = server[server.index("40, 41, 42:"):server.index("31, 50:")]
        self.assertIn("气缸_提交(缸号 := ui轴号", branch)
        self.assertIn("Runtime.aw气缸命令[ui轴号] := st请求[3];", branch)
        self.assertIn("Runtime.aw气缸序列[ui轴号] := st请求[4];", branch)

    def test_server_has_no_dead_stop_outputs(self):
        server = st("03_pou/功能块_服务端.st")
        for dead in ("StopAxisRequested", "StopCylinderRequested", "StopObject"):
            self.assertNotIn(dead, server)
        self.assertIn("StopAllRequested", server)

    def test_server_publishes_bound_cylinders_from_consumer_state(self):
        server = st("03_pou/功能块_服务端.st")
        publish = server[server.index("FOR i循环 := 0 TO 53 DO\n        ui基址 := XJV1_CYLINDER_CONFIG_BASE"):]
        publish = publish[:publish.index("FOR i循环 := 0 TO 119 DO")]
        self.assertIn("(lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0", publish)
        self.assertIn("XJV1_STATUS_CYLINDER_SUMMARY_OFFSET", publish)
        self.assertIn("Runtime.ast气缸[i循环].b故障", publish)
        self.assertIn("Runtime.ast气缸[i循环].w错误码", publish)
        self.assertIn("XJV1_CYLINDER_LIVE_PERMIT_OFFSET", publish)
        self.assertIn("XJV1_CYLINDER_LIVE_ALARM_OFFSET", publish)
        self.assertIn("Published[ui基址 + XJV1_CYLINDER_LIVE_REASON_OFFSET] := 4;", publish)

    def test_cylinder_alarm_joins_bound_traversal_only(self):
        server = st("03_pou/功能块_服务端.st")
        self.assertIn("ab上次气缸故障 : ARRAY[0..53] OF BOOL", server)
        traversal = server[server.index("ab上次气缸故障"):]
        self.assertIn("16#0200", traversal)

    def test_prg_instantiates_cylinder_consumers_without_wired_outputs(self):
        prg = st("04_program/程序_主循环.st")
        self.assertIn("fb气缸调度 : 功能块_气缸调度;", prg)
        self.assertIn("b输出6 := FALSE;", prg)
        self.assertIn("b输出7 := FALSE;", prg)
        loop = st("03_pou/功能块_气缸调度.st")
        for field in ("DelayMs", "HomeDelayMs", "TimeoutMs", "HasWorkSensor", "HasOriginSensor", "Token", "CancelMode"):
            self.assertIn(field + " :=", loop)
        self.assertIn("ab气缸模块就绪[i] AND afb驱动[i].WorkOutput", loop)
        self.assertIn("ab气缸模块就绪[i] AND afb驱动[i].OriginOutput", loop)
        hardware = st("02_gvl/全局变量_硬件.gvl.st")
        for array in ("ab气缸动点传感器", "ab气缸原点传感器",
                      "ab气缸动点输出", "ab气缸原点输出"):
            self.assertIn(f"{array} : ARRAY[0..53] OF BOOL;", hardware)

    def test_server_cylinder_live_stays_unpublished_until_wired(self):
        server = st("03_pou/功能块_服务端.st")
        self.assertIn("XJV1_STATUS_CYLINDER_BOUND_OFFSET + i循环", server)
        self.assertIn("XJV1_STATUS_CYLINDER_ONLINE_OFFSET + i循环", server)
        self.assertIn("AND ab气缸映射已核验[i循环] AND ab气缸模块就绪[i循环]", server)


class CylinderUpgradeTests(unittest.TestCase):
    def test_legacy_migration_preserves_axis_and_points(self):
        text = st("03_pou/功能块_配置.st")
        migration = text.split("IF Store.dw签名 = DWORD#16#584A5632 THEN", 1)[1].split("IF Store.dw签名 <> XJV1_SIGNATURE", 1)[0]
        self.assertIn("Store.aw气缸配置[i循环, 7] := Store.aw气缸配置[i循环, 5]", migration)
        self.assertIn("Store.b已确认 := FALSE", migration)
        self.assertNotIn("Store.aw轴配置", migration)
        self.assertNotIn("Store.aw点位", migration)
        for field in ("aw类型", "aw动点输出", "aw原点输出", "aw动点输入", "aw原点输入"):
            self.assertIn("全局变量_气缸工程." + field, text)

    def test_token_queries_reject_zero_and_stale_owner(self):
        for name in ("完成", "忙", "故障"):
            text = st(f"03_pou/气缸_{name}.st")
            self.assertIn("请求号 : UDINT", text)
            self.assertIn("请求号 = 0", text)
            self.assertIn("udi请求号", text)
        done = st("03_pou/气缸_完成.st")
        self.assertIn("udi完成号 = 请求号", done)
        submit = st("03_pou/气缸_提交.st")
        self.assertIn("函数_动作许可", submit)
        self.assertIn("命令 <> 42", submit)
        self.assertIn("UDINT#4294967295", submit)

    def test_cancel_covers_unissued_requests_and_never_replays(self):
        text = st("03_pou/功能块_气缸调度.st")
        for guard in ("IF Runtime.b暂停 THEN by取消 := 1", "IF StopAll OR NOT b绑定",
                      "IF NOT Runtime.bHMI在线", "Runtime.b硬急停 OR Runtime.b软急停",
                      "b待下发 := FALSE", "udi完成号 := 0"):
            self.assertIn(guard, text)
        driver = st("03_pou/功能块_气缸.st")
        self.assertIn("ELSIF ValveType = 3 THEN\n        OriginOutput := FALSE", driver)
        self.assertIn("udi活动请求 := 0; DoneToken := 0; i目标侧 := 0; Moving := FALSE", driver)
        self.assertNotIn("NOT b上次执行", driver)

    def test_mapping_validation_rejects_output_aliasing(self):
        text = st("03_pou/气缸_配置有效.st")
        self.assertIn("FOR i := 0 TO 53", text)
        self.assertIn("Store.aw气缸配置[缸号, j] = Store.aw气缸配置[i, k]", text)
        self.assertIn("WORD#16#FFF0", text)


class WatchdogLeaseTests(unittest.TestCase):
    def test_jog_lease_starts_without_online_gate_and_cancels_offline(self):
        text = st("03_pou/功能块_看门狗.st")
        self.assertIn("IF StartJog THEN", text)
        self.assertNotIn("IF StartJog AND Online", text)
        self.assertIn("IF JogActive AND (StopJog OR NOT Online OR tmr点动.Q) THEN", text)

    def test_config_epoch_is_shared_input_that_no_caller_passes(self):
        text = st("03_pou/功能块_配置.st")
        inputs = text.split("VAR_INPUT", 1)[1].split("END_VAR", 1)[0]
        self.assertIn("Epoch : WORD", inputs)
        self.assertIn("omit from ordinary FB calls", inputs)
        for caller in ("03_pou/功能块_服务端.st", "../tests/程序_自测.st"):
            body = (ROOT / caller).resolve().read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?<!\.)\bEpoch\s*:=", body),
                              f"{caller} must not pass Epoch explicitly")


if __name__ == "__main__":
    unittest.main()
