"""XS Studio interface constraints; these checks do not execute IEC code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "plc/src/03_pou"


def test_shared_state_is_not_written_through_output_only_parameters():
    for filename, names in (
        ("功能块_配置.st", ("Epoch",)),
    ):
        text = (ROOT / filename).read_text(encoding="utf-8")
        inputs = text.split("VAR_INPUT", 1)[1].split("END_VAR", 1)[0]
        outputs = text.split("VAR_OUTPUT", 1)[1].split("END_VAR", 1)[0]
        for name in names:
            assert f"{name} :" in inputs
            assert f"{name} :" not in outputs
