from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_xs_tools_resolve_paths_from_repository_root():
    tools = ROOT / "plc/tools"
    for path in tools.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "motion_task.py":
            # Pure task migration helper: no files or repository paths to resolve.
            assert "projects.open" not in text and "open(" not in text
            continue
        assert "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))" in text
