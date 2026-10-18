#!/usr/bin/env python3
"""Generate the KSUN/SUSFS fragment from the current build's selected features."""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/ksun-susfs-6.1.config"
CUSTOM = ROOT / "configs/custom.config"
LTO_SYMBOLS = {"noneLTO": "CONFIG_LTO_NONE", "thinLTO": "CONFIG_LTO_CLANG_THIN",
               "fullLTO": "CONFIG_LTO_CLANG_FULL"}


def fragment(base, lto, bbg, networking):
    if lto not in LTO_SYMBOLS or bbg not in ("true", "false") or networking not in ("true", "false"):
        raise ValueError("Invalid LTO, BBG or Networking input")
    matches = re.findall(r'^CONFIG_LSM="([A-Za-z0-9_,]+)"$', base, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Base .config must contain one quoted CONFIG_LSM list")
    lsm = [name for name in matches[0].split(",") if name != "baseband_guard"]
    if "selinux" not in lsm:
        raise ValueError("Base CONFIG_LSM is missing selinux")
    if bbg == "true":
        lsm.append("baseband_guard")
    lines = [CORE.read_text().rstrip(), f"CONFIG_BBG={'y' if bbg == 'true' else 'n'}",
             'CONFIG_LSM="' + ",".join(lsm) + '"']
    lines += [f"{symbol}={'y' if mode == lto else 'n'}" for mode, symbol in LTO_SYMBOLS.items()]
    if networking == "true":
        marker = "# Networking extras\n"
        custom = CUSTOM.read_text()
        if custom.count(marker) != 1:
            raise ValueError("Networking extras section is missing or ambiguous")
        lines.append(custom.split(marker, 1)[1].rstrip())
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="This build's gki_defconfig output")
    parser.add_argument("output", type=Path)
    parser.add_argument("--lto", choices=LTO_SYMBOLS, required=True)
    parser.add_argument("--bbg", choices=("true", "false"), required=True)
    parser.add_argument("--networking", choices=("true", "false"), required=True)
    args = parser.parse_args(argv)
    try:
        text = fragment(args.base.read_text(), args.lto, args.bbg, args.networking)
        args.output.write_text(text)
        print(f"Requested config: LTO={args.lto}, BBG={args.bbg}, Networking={args.networking}")
        return 0
    except (OSError, ValueError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
