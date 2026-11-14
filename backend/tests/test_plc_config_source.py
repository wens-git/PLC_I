"""ST source acceptance contracts, not PLC compilation or ST execution.

These guard the transaction boundaries and protocol-critical source constructs.
Compiler, scan-level behavior and power-loss acceptance remain separate checks.
"""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plc/src"


def read(relative):
    return (SRC / relative).read_text(encoding="utf-8")


def code():
    return re.sub(r"\(\*.*?\*\)", "", read("03_pou/功能块_配置.st"), flags=re.S)


class PlcConfigSourceTests(unittest.TestCase):
    def test_retained_layout_matches_protocol_capacities(self):
        schema = json.loads((ROOT / "docs/protocol-v1.json").read_text(encoding="utf-8"))
        text = read("01_types/结构体_配置.st")
        names = {"axis_config": "aw轴配置", "cylinder_config": "aw气缸配置", "points": "aw点位"}
        for window in schema["windows"]:
            if window["id"] in names:
                self.assertRegex(text, rf'{names[window["id"]]}\s*:\s*ARRAY\[0\.\.{window["count"] - 1},\s*0\.\.{window["stride"] - 1}\] OF WORD')
        self.assertIn("dw签名 : DWORD", text)
        self.assertIn("b已确认 : BOOL", text)
        self.assertNotIn("Epoch", text)
        self.assertNotIn("Names", re.sub(r"\(\*.*?\*\)", "", text, flags=re.S))
        retain = read("02_gvl/全局变量_保持区.gvl.st")
        self.assertIn("VAR_GLOBAL PERSISTENT RETAIN", retain)
        self.assertIn("Store : 结构体_配置", retain)

    def test_fb_interface_and_scan_contract(self):
        text = code()
        for fragment in ("FUNCTION_BLOCK 功能块_配置", "Execute : BOOL",
                         "Request : 类型_命令区", "Result : WORD", "Epoch : WORD",
                         "VAR_IN_OUT", "Store : 结构体_配置", "END_FUNCTION_BLOCK"):
            self.assertIn(fragment, text)
        self.assertNotIn("METHOD", text)
        self.assertLess(text.index("Store.dw签名 <> XJV1_SIGNATURE"),
                        text.index("IF NOT Execute THEN RETURN; END_IF"))

    def test_cold_defaults_are_safe_and_complete(self):
        text = code().split("IF NOT Execute THEN RETURN; END_IF")[0]
        for fragment in ("FOR i循环 := 0 TO 15", "FOR i循环 := 0 TO 53", "FOR i循环 := 0 TO 119",
                         "Store.aw气缸配置[i循环, i子循环] := WORD#16#FFFF",
                         "Store.aw气缸配置[i循环, 5] := 200", "Store.aw气缸配置[i循环, 6] := 3000",
                         "Store.aw点位[i循环, 4] := SHL(INT_TO_WORD(i循环), 2)",
                         "Store.aw点位[i循环, 4] := XJV1_POINT_FREE", "Store.b已确认 := FALSE"):
            self.assertIn(fragment, text)
        self.assertNotIn("Names", text)
        self.assertLess(text.index("Store.b已确认 := FALSE"),
                        text.index("Store.dw签名 := XJV1_SIGNATURE"))
        self.assertIn("lw已绑定气缸 : LWORD := 全局变量_气缸工程.lw绑定", read("02_gvl/全局变量_绑定.gvl.st"))
        self.assertIn("lw绑定 : LWORD := 0", read("02_gvl/全局变量_气缸工程.gvl.st"))

    def test_envelope_binding_and_epoch_precede_candidate_commit(self):
        text = code()
        for fragment in ("Result := 函数_校验(Request := Request)",
                         "全局变量_绑定.w已绑定轴",
                         "全局变量_绑定.lw已绑定气缸",
                         "IF (w命令码 = 50) AND (Request[9] <> Epoch) THEN Result := 16; RETURN; END_IF"):
            self.assertIn(fragment, text)
        self.assertLess(text.index("Result := 函数_校验"), text.index("SHL(WORD#1, i轴号)"))
        self.assertLess(text.index("(Request[9] <> Epoch)"), text.index("Store.aw轴配置[i索引, i子循环] := aw候选[i子循环]"))

    def test_masked_updates_start_from_full_current_record(self):
        text = code()
        for fragment in ("aw候选[i子循环] := Store.aw轴配置[i索引, i子循环]",
                         "aw候选[i子循环] := Store.aw气缸配置[i索引, i子循环]",
                         "aw候选[i子循环] := Store.aw点位[i点位索引, i子循环]",
                         "w掩码 AND SHL(WORD#1, i循环)", "w掩码 AND WORD#16#0080",
                         "w掩码 AND WORD#16#0001", "w掩码 AND WORD#16#0002",
                         "w掩码 AND WORD#16#0004"):
            self.assertIn(fragment, text)
        self.assertIn("Request[16 + i子循环] <> Store.aw气缸配置[i索引, i子循环]", text)
        self.assertIn("FOR i子循环 := 24 TO 31", text)
        self.assertIn("FOR i子循环 := 21 TO 31", text)

    def test_complete_candidates_validate_before_runtime_writes(self):
        text = code()
        for fragment in ("di负限位 >= di正限位", "dw值 > DWORD#2147483647",
                         "aw候选[5] >= aw候选[6]", "aw候选[7] >= aw候选[6]", 
                         "Result := 14; RETURN", "aw候选[14] AND WORD#16#FFFE",
                         "aw候选[4] AND NOT XJV1_POINT_VALID_MASK",
                         "di位置 < di负限位", "di位置 > di正限位"):
            self.assertIn(fragment, text)
        self.assertLess(text.index("di负限位 >= di正限位"), text.index("Store.aw轴配置[i索引, i子循环] := aw候选[i子循环]"))
        self.assertLess(text.index("aw候选[5] >= aw候选[6]"), text.index("Store.aw气缸配置[i索引, i子循环] := aw候选[i子循环]"))
        self.assertLess(text.index("di位置 < di负限位"), text.index("Store.aw点位[i点位索引, i子循环] := aw候选[i子循环]"))

    def test_point_pool_ownership_contract(self):
        """Free slot is exactly XJV1_POINT_FREE; owner 16 is the internal free marker so axis 15 is usable."""
        text = code()
        for fragment in ("i点位索引 := WORD_TO_INT(Request[7] AND WORD#16#00FF)",
                         "IF Store.aw点位[i索引, 4] = XJV1_POINT_FREE THEN",
                         "i归属 := WORD_TO_INT(SHR(Store.aw点位[i索引, 4], 2) AND WORD#16#000F)",
                         "(i归属 <> i轴号) AND (i归属 <> 16) THEN Result := 18",
                         "aw候选[4] := SHL(INT_TO_WORD(i轴号), 2) OR WORD#16#0002",
                         "IF w命令码 <> 50 THEN Result := 4; RETURN; END_IF",
                         "IF aw候选[4] = XJV1_POINT_FREE THEN",
                         "(i新归属 <> i归属) AND (i新归属 <> 16) THEN Result := 9",
                         "(i新归属 = 16) AND ((Store.aw点位[i点位索引, 4] AND WORD#16#0001) <> 0)",
                         "(i新归属 = 16) AND (i点位索引 = i归属)",
                         "AND (Request[20] <> XJV1_POINT_FREE) THEN",
                         "Request[20] AND NOT XJV1_POINT_VALID_MASK",
                         "(Request[20] AND XJV1_POINT_FREE) <> 0) AND (Request[20] <> XJV1_POINT_FREE)",
                         "Request[20] AND WORD#16#0002",
                         "Store.aw点位[i点位索引, 4] AND WORD#16#0002",
                         "(aw候选[4] AND WORD#16#0003) = WORD#16#0001",
                         "IF i新归属 <> 16 THEN",
                         "SHL(WORD#1, i新归属)"):
            self.assertIn(fragment, text)
        self.assertNotIn("w归属 = 15", text)
        self.assertNotIn("003C", text)
        self.assertNotIn("WSTRING", text)
        self.assertNotIn("* 20", text)

    def test_no_name_storage_in_plc(self):
        text = code()
        for fragment in ("Names", "NameIndex", "NeedLow", "Code = 51", "Code <> 51"):
            self.assertNotIn(fragment, text)

    def test_success_alone_advances_epoch_and_clears_confirmation(self):
        text = code()
        self.assertEqual(text.count("Epoch := 0"), 1)
        self.assertEqual(text.count("Epoch := Epoch + 1"), 1)
        # code() strips comments, so anchor on the first commit write.
        commit = text[text.rindex("FOR i子循环 := 0 TO 15 DO Store.aw轴配置[i索引, i子循环] := aw候选[i子循环]"):]
        self.assertIn("Store.b已确认 := FALSE", commit)
        self.assertIn("IF Epoch = WORD#16#FFFF THEN", commit)
        self.assertLess(commit.index("Store.b已确认 := FALSE"), commit.index("Epoch := Epoch + 1"))
        self.assertTrue(text.rstrip().endswith("END_FUNCTION_BLOCK"))

    def test_no_runtime_mutation_before_shared_commit_boundary(self):
        transaction = code().split("IF NOT Execute THEN RETURN; END_IF;")[1]
        first_write = re.search(r"Store\.\w+\[[^\]]+\]\s*:=", transaction)
        self.assertIsNotNone(first_write)
        validation = transaction[:first_write.start()]
        commit = transaction[first_write.start():]
        self.assertNotRegex(validation, r"(?:Store\.\w+|Epoch)\s*:=")
        self.assertNotIn("RETURN", commit)
        self.assertEqual(len(re.findall(r"Store\.\w+\[[^\]]+\]\s*:=", commit)), 3)
        self.assertEqual(commit.count("Result :="), 1)

    def test_dependency_validates_full_width_arguments_before_narrowing(self):
        text = read("03_pou/函数_校验.st")
        for fragment in ("dw参数A := SHL(WORD_TO_DWORD(Request[6]), 16)",
                         "dw参数B := SHL(WORD_TO_DWORD(Request[8]), 16)",
                         "dw参数C := SHL(WORD_TO_DWORD(Request[10]), 16)",
                         "dw参数A >= 120", "dw参数B > 65535", "dw参数A > 65535", "dw参数A > 255",
                         "dw参数A > 7", "dw参数C > 2147483647", "w类别 <> 1", "w类别 = 0",
                         "i索引 >= 16", "i索引 >= 54", "i索引 >= 120"):
            self.assertIn(fragment, text)
        self.assertLess(code().index("IF Result <> 0 THEN RETURN; END_IF"),
                        code().index("w掩码 := Request[7]"))


if __name__ == "__main__":
    unittest.main()
