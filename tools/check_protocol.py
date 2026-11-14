"""Generate/check shared wire maps. This is not an XS Studio compiler."""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUDGET = {"holding": 32, "input": 1830}
AREAS = {"holding": "Holding Register（FC03 读 / FC06、FC16 写）", "input": "Input Register（FC04 只读）"}


def validate(spec):
    """Windows of one area must tile 0..size-1 without gaps or overlap."""
    errors = []
    cursor = {area: 0 for area in AREAS}
    for w in spec["windows"]:
        area = w.get("area")
        if area not in AREAS:
            errors.append(f"{w['id']}: unknown area {area!r}")
            continue
        if w["base"] != cursor[area]:
            errors.append(f"{w['id']}: base {w['base']} != expected {cursor[area]}")
        if w["end"] != w["base"] + w["stride"] * w["count"] - 1:
            errors.append(f"{w['id']}: end does not match stride*count")
        if (area == "holding") != (w["access"] == "write"):
            errors.append(f"{w['id']}: access must be write only for holding windows")
        used = 0
        for f in w["fields"]:
            if f["offset"] != used:
                errors.append(f"{w['id']}.{f['id']}: offset {f['offset']} != {used}")
            used = f["offset"] + f["words"]
        if used != w["stride"]:
            errors.append(f"{w['id']}: fields cover {used} of {w['stride']} words")
        cursor[area] = w["end"] + 1
    if cursor != spec["areas"]:
        errors.append(f"area sizes {cursor} != declared {spec['areas']}")
    # Frozen 1.2 budget: names live on the host and occupy no PLC register.
    if spec["areas"] != BUDGET:
        errors.append(f"register budget {spec['areas']} != frozen {BUDGET}")
    if spec["transport"]["port"] != 1502:
        errors.append("production Modbus TCP port must be 1502")
    if any(w["id"] == "names" for w in spec["windows"]):
        errors.append("names window must not exist: names are host-owned")
    codes = [c["code"] for c in spec["commands"]]
    if 51 in codes or any(b["code"] == 51 for bits in spec["permit_bits"].values() for b in bits):
        errors.append("command 51 (PLC name commit) is retired")
    flags = spec["point_flags"]
    if flags["free"] & (flags["owner_mask"] << flags["owner_shift"]) or flags["free"] & 3:
        errors.append("point free flag must not overlap owner/enable/taught bits")
    alarm_codes = [a["code"] for a in spec["alarms"]]
    if len(alarm_codes) != len(set(alarm_codes)) or any(not a["message"] or not a["action"] for a in spec["alarms"]):
        errors.append("alarm catalogue needs unique codes with message and action")
    if errors:
        raise SystemExit("Protocol schema errors:\n" + "\n".join(errors))


def render_markdown(spec):
    rows = ["# XJV1 Register Map", "", "Generated from `protocol-v1.json`. Do not edit by hand.", "",
            f"Revision {spec['revision']}, signature 0x{spec['signature']:08X}, Modbus TCP port "
            f"{spec['transport']['port']}, Unit ID {spec['transport']['unit']}. All addresses are zero-based PDU addresses.", "",
            "| Area | Words | Functions |", "|---|---|---|"]
    rows += [f"| {area} | {spec['areas'][area]} | {AREAS[area]} |" for area in AREAS]
    rows += [f"| names | 0 | host configuration store, no PLC register |",
             f"| total | {sum(spec['areas'].values())} | {2 * sum(spec['areas'].values())} bytes |"]
    rows += ["", "| Window | Area | Base | End | Stride | Count | Access |", "|---|---|---|---|---|---|---|"]
    for w in spec["windows"]:
        rows.append(f"| {w['id']} | {w['area']} | {w['base']} | {w['end']} | {w['stride']} | {w['count']} | {w['access']} |")
    for w in spec["windows"]:
        rows += ["", f"## {w['id']}", "", "| Field | Offset | Words | Type |", "|---|---|---|---|"]
        rows += [f"| {f['id']} | +{f['offset']} | {f['words']} | {f['type']} |" for f in w["fields"]]
    for kind, fields in spec["field_masks"].items():
        rows += ["", f"## {kind} Field Masks", "", "| Field | Mask |", "|---|---|"]
        rows += [f"| {f['id']} | 0x{f['mask']:04X} |" for f in fields]
    for kind, bits in spec["permit_bits"].items():
        rows += ["", f"## {kind} Permit Bits", "", "| Bit | Command |", "|---|---|"]
        rows += [f"| {b['bit']} | {b['code']} |" for b in bits]
    flags = spec["point_flags"]
    rows += ["", "## Point Flags", "",
             f"bit0 enabled, bit1 taught, bit{flags['owner_shift']}..{flags['owner_shift'] + 3} owner axis 0..15, "
             f"0x{flags['free']:04X} free slot (owner bits zero, not enabled, not taught). Other bits are zero."]
    rows += ["", "## Alarms", "", "| Code | Object | Message | Action |", "|---|---|---|---|"]
    rows += [f"| {a['code']} | {a['object']} | {a['message']} | {a['action']} |" for a in spec["alarms"]]
    rows += ["", "## Rejections", "", "| Code | Message | Action |", "|---|---|---|"]
    rows += [f"| {r['code']} | {r['message']} | {r['action']} |" for r in spec["rejections"]]
    return "\n".join(rows) + "\n"


def render_st(spec):
    signature = spec["signature"]
    lines = ["(* Generated by tools/check_protocol.py --write. *)", "VAR_GLOBAL CONSTANT",
             f"    XJV1_SIGNATURE : DWORD := DWORD#16#{signature:08X};",
             f"    XJV1_SIGNATURE_HI : WORD := WORD#16#{signature >> 16:04X};",
             f"    XJV1_SIGNATURE_LO : WORD := WORD#16#{signature & 0xFFFF:04X};",
             f"    XJV1_MODBUS_PORT : UINT := {spec['transport']['port']};",
             f"    XJV1_HOLDING_WORDS : UINT := {spec['areas']['holding']};",
             f"    XJV1_INPUT_WORDS : UINT := {spec['areas']['input']};",
             f"    XJV1_POINT_FREE : WORD := WORD#16#{spec['point_flags']['free']:04X};",
             f"    XJV1_POINT_VALID_MASK : WORD := WORD#16#{spec['point_flags']['valid_mask']:04X};"]
    for w in spec["windows"]:
        prefix = "XJV1_" + w["id"].upper()
        lines += [f"    {prefix}_BASE : UINT := {w['base']};",
                  f"    {prefix}_STRIDE : UINT := {w['stride']};",
                  f"    {prefix}_COUNT : UINT := {w['count']};"]
        for f in w["fields"]:
            lines.append(f"    {prefix}_{f['id'].upper()}_OFFSET : UINT := {f['offset']};")
    lines += ["END_VAR", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate derived tables")
    args = parser.parse_args()
    spec = json.loads((ROOT / "docs/protocol-v1.json").read_text(encoding="utf-8"))
    validate(spec)
    artifacts = {ROOT / "docs/register-map.md": render_markdown(spec),
                 ROOT / "plc/src/02_gvl/全局变量_地址表.gvl.st": render_st(spec)}
    for path, text in artifacts.items():
        if args.write:
            path.write_text(text, encoding="utf-8", newline="\n")
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            raise SystemExit(f"Protocol drift: {path.relative_to(ROOT)}")
    print(f"Register budget: holding {spec['areas']['holding']} + input {spec['areas']['input']} = "
          f"{sum(spec['areas'].values())} WORD; names 0 WORD (host-owned).")
    print("Protocol artifact check: 0 errors (no PLC compilation performed).")


if __name__ == "__main__":
    main()
