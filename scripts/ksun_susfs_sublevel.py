#!/usr/bin/env python3
"""Resolve KSUN + SUSFS sublevels from the current Manual Update pins.

  resolve SUBLEVEL     lts/auto/empty follows KERNEL_COMMIT_6_1; a number uses its pin.
  commit SUBLEVEL      Print the same kernel commit used by the other variants.
  record REPO COMMIT   Optional historical replay report; never needed to unlock builds.

Source availability and the real SUSFS minimum (6.1.167) are checked here.
Patch applicability is checked against the selected source during staging.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gkid_parity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "kernel-patches/susfs/6.1-v2"
FEATURE_LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"  # historical record command only
UPSTREAM_LOCK = ROOT / "configs/upstream.lock"
MIN_SUBLEVEL = 167
MANIFESTS = (BASE / "replay/kernel-replay.json", BASE / "features/kernel-replay.json")
SHA = re.compile(r"[0-9a-f]{40}")


def git(repo, *args, env=None, data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                            env=env, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: "
                           + result.stderr.decode(errors="replace").strip()[:1500])
    return result.stdout.decode().strip()


def series(manifest):
    """Patch bytes of a replay manifest, each checked against its SHA256."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    patches = []
    for entry in data["patches"]:
        raw = (manifest.parent / entry["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"checksum mismatch: {entry['path']}")
        patches.append((entry["path"], raw))
    return patches


def identities(repo, commit, lock):
    if not SHA.fullmatch(commit):
        raise ValueError("COMMIT must be a full 40-character SHA")
    makefile = git(repo, "show", f"{commit}:Makefile")
    fields = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL) = (\d+)$", makefile, re.MULTILINE))
    if (fields.get("VERSION"), fields.get("PATCHLEVEL")) != ("6", "1") or "SUBLEVEL" not in fields:
        raise ValueError("COMMIT is not a 6.1 kernel")
    meta = lock["frozen_core"]
    core, features = (series(manifest) for manifest in MANIFESTS)
    with tempfile.TemporaryDirectory(prefix="ksun-susfs-sublevel-") as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        git(repo, "read-tree", commit, env=env)

        def apply(patches):
            for name, raw in patches:
                try:
                    git(repo, "apply", "--cached", "-", env=env, data=raw)
                except RuntimeError as exc:
                    raise RuntimeError(f"{name} does not apply: {exc}") from None
            return git(repo, "write-tree", env=env)

        core_tree = apply(core)
        frozen = dict(env, GIT_AUTHOR_NAME=meta["author_name"], GIT_AUTHOR_EMAIL=meta["author_email"],
                      GIT_AUTHOR_DATE=meta["author_date"], GIT_COMMITTER_NAME=meta["committer_name"],
                      GIT_COMMITTER_EMAIL=meta["committer_email"],
                      GIT_COMMITTER_DATE=meta["committer_date"])
        snapshot = git(repo, "commit-tree", core_tree, "-p", commit, env=frozen,
                       data=meta["message"].encode())
        integrated = apply(features)
        # Plain android14-6.1-lts sublevels get Cogan's GKID-equivalent stack on top.
        stack = gkid_parity.has_stack(git(repo, "show", f"{commit}:{gkid_parity.VERSION_C}"))
        if not stack:
            gkid_parity.apply(repo, cached=True, env=env)
        final = git(repo, "write-tree", env=env)
    return fields["SUBLEVEL"], {"kernel_commit": commit, "core_kernel_tree": core_tree,
                                "kernel_snapshot": snapshot, "integrated_kernel_tree": integrated,
                                "gkid_stack": stack, "final_kernel_tree": final}


def read_pins(path=None):
    pins = {}
    for line in (path or UPSTREAM_LOCK).read_text(encoding="utf-8").splitlines():
        if line.startswith("KERNEL_COMMIT_6_1") and "=" in line:
            key, value = line.split("=", 1)
            if re.fullmatch(r"KERNEL_COMMIT_6_1(?:_[0-9]+)?", key):
                if not SHA.fullmatch(value):
                    raise ValueError(f"Invalid kernel pin: {key}")
                pins[key] = value
    return pins


def resolve(value, pins):
    available = sorted(int(key.removeprefix("KERNEL_COMMIT_6_1_")) for key in pins
                       if re.fullmatch(r"KERNEL_COMMIT_6_1_[0-9]+", key))
    wanted = value.strip().lower()
    if wanted in ("", "lts", "auto"):
        matches = [n for n in available if pins[f"KERNEL_COMMIT_6_1_{n}"] == pins.get("KERNEL_COMMIT_6_1")]
        if not matches:
            raise ValueError("Current kernel pin has no sublevel entry; run Cogan Manual Update")
        wanted = str(max(matches))
    if not re.fullmatch(r"[1-9][0-9]*", wanted) or int(wanted) not in available:
        raise ValueError(f"Kernel sublevel {value!r} is not available; use lts or one of: "
                         + " ".join(str(n) for n in available if n >= MIN_SUBLEVEL))
    if int(wanted) < MIN_SUBLEVEL:
        raise ValueError(f"SUSFS variants need kernel 6.1.{MIN_SUBLEVEL} or newer (requested 6.1.{wanted})")
    return wanted


def commit(value, pins):
    result = pins[f"KERNEL_COMMIT_6_1_{resolve(value, pins)}"]
    if not SHA.fullmatch(result):
        raise ValueError("Kernel pin must be a full SHA")
    return result


def main(argv):
    try:
        if len(argv) == 3 and argv[1] == "resolve":
            print(resolve(argv[2], read_pins()))
            return 0
        if len(argv) == 3 and argv[1] == "commit":
            print(commit(argv[2], read_pins()))
            return 0
        if len(argv) == 4 and argv[1] == "record":
            lock = json.loads(FEATURE_LOCK.read_text(encoding="utf-8"))
            sublevel, entry = identities(Path(argv[2]), argv[3], lock)
            print(json.dumps({sublevel: entry}, indent=2))
            return 0
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc)[:2000], file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
