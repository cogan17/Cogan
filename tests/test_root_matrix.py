#!/usr/bin/env python3
"""Fast offline regression tests; no GitHub Actions build required."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "py" / "generate-matrix.py"

def run(manager, susfs=False, version="6.1", extra=None):
    env = os.environ.copy()
    for key in ("BUILD_VANILLA", "BUILD_KSU", "BUILD_KSUN", "BUILD_KSU_SUSFS"):
        env.pop(key, None)
    env.update({
        "ROOT_MANAGER": manager,
        "ENABLE_SUSFS": str(susfs).lower(),
        "KERNEL_VERSION": version,
    })
    env.update(extra or {})
    return subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)

for manager, ksu, susfs in [
    ("KernelSU-Next", "KSUN", False),
    ("KernelSU", "KSU", False),
    ("KernelSU", "KSU", True),
    ("BakaSU", "BSU", True),
    ("No Root", "no", False),
]:
    result = run(manager, susfs)
    assert result.returncode == 0, (manager, result.stderr)
    entries = json.loads(result.stdout.split("matrix=", 1)[1])["include"]
    assert len(entries) == 1, (manager, entries)
    assert entries[0]["KSU"] == ksu
    assert entries[0]["KSU_SUSFS"] == str(susfs).lower()

for manager, susfs in [("KernelSU-Next", True), ("No Root", True), ("BakaSU", False)]:
    assert run(manager, susfs).returncode != 0, manager

legacy = run("Legacy")
assert legacy.returncode == 0, legacy.stderr
assert len(json.loads(legacy.stdout.split("matrix=", 1)[1])["include"]) == 9
assert run("KernelSU-Next", version="bogus").returncode != 0
assert len(json.loads(run("Legacy", version="All").stdout.split("matrix=", 1)[1])["include"]) == 45
assert len(json.loads(run("Legacy", extra={"BUILD_KSUN": "true"}).stdout.split("matrix=", 1)[1])["include"]) == 10
print("PASS: root manager matrix regression checks")
