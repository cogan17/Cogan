#!/usr/bin/env python3
"""Stage built-in KSUN + SUSFS on the current selected Manual Update kernel pin.

Usage: stage_ksun_susfs_candidate.py KERNEL_DIR KSUN_DIR [SUBLEVEL]

No historical tree/config/build evidence is needed. Each selected patch is
checksum-verified and preflighted on the actual source before it is applied.
BBG and NETWORKING follow the build environment (true/false, default true).
NoMount stays bundled. Source pins and the SUSFS-compatible KSUN fork are retained.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gkid_parity  # noqa: E402
import ksun_susfs_sublevel as sublevels  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "kernel-patches/susfs/6.1-v2"
SOURCE_LOCK = ROOT / "configs/ksun-susfs-6.1-v2.lock.json"
REPLAY = ROOT / "scripts/ksun_susfs_replay.py"


def git(repo, *args, env=None, data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            input=data, text=True, env=env, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def enabled(name):
    value = os.environ.get(name, "true")
    if value not in ("true", "false"):
        raise ValueError(f"{name} must be true or false")
    return value == "true"


def replay(tree, manifest, head, excluded=()):
    command = [sys.executable, str(REPLAY), str(tree), str(manifest), "--apply",
               "--kernel-commit", head]
    for name in excluded:
        command += ["--exclude-patch", name]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    print(result.stdout, end="")
    if result.returncode:
        raise RuntimeError(f"Replay {manifest.name} failed: {result.stderr.strip()[:1000]}")


def expect(label, actual, expected):
    if actual != expected:
        raise RuntimeError(f"{label}: got {actual}, expected {expected}")
    print(f"[+] {label}: {actual}")


def snapshot(repo):
    """Make a clean replay boundary from this build's source, without old tree IDs."""
    git(repo, "add", "-A")
    tree, parent = git(repo, "write-tree"), git(repo, "rev-parse", "HEAD")
    date = git(repo, "show", "-s", "--format=%cI", "HEAD")
    env = {**os.environ, "GIT_AUTHOR_NAME": "Cogan source staging",
           "GIT_AUTHOR_EMAIL": "source-staging@example.invalid", "GIT_AUTHOR_DATE": date,
           "GIT_COMMITTER_NAME": "Cogan source staging",
           "GIT_COMMITTER_EMAIL": "source-staging@example.invalid", "GIT_COMMITTER_DATE": date}
    commit = git(repo, "commit-tree", tree, "-p", parent, env=env,
                 data="Cogan KSUN/SUSFS source stage\n")
    git(repo, "reset", "-q", "--soft", commit)
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError(f"{repo.name} not clean after source snapshot")
    print(f"[+] {repo.name} core tree: {tree}")
    return commit


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    kernel, ksun = Path(argv[1]).resolve(), Path(argv[2]).absolute()
    try:
        bbg, networking = enabled("BBG"), enabled("NETWORKING")
        pins = sublevels.read_pins()
        sublevel = sublevels.resolve(argv[3] if len(argv) == 4 else "lts", pins)
        kernel_commit = sublevels.commit(sublevel, pins)
        expect("kernel checkout", git(kernel, "rev-parse", "HEAD"), kernel_commit)
        makefile = git(kernel, "show", "HEAD:Makefile")
        fields = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL) = (\d+)$", makefile, re.MULTILINE))
        if fields != {"VERSION": "6", "PATCHLEVEL": "1", "SUBLEVEL": sublevel}:
            raise ValueError("Kernel Makefile does not match the selected 6.1 sublevel")
        if git(kernel, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("kernel checkout is dirty; refusing staging")
        if ksun.exists() or ksun.is_symlink():
            raise RuntimeError(f"{ksun} already exists")
        if ksun.parent != kernel.parent:
            raise RuntimeError("KSUN must be a sibling of the kernel checkout (drivers/kernelsu -> ../../ksun/kernel)")

        sources = json.loads(SOURCE_LOCK.read_text())
        ksun_pin = sources["sources"]["ksun"]
        manifest = json.loads((BASE / "replay/ksun-replay.json").read_text())
        expect("KSUN manifest pin", manifest["kernel_commit"], ksun_pin["commit"])
        ksun.mkdir()
        git(ksun, "init", "-q")
        git(ksun, "fetch", "-q", "--depth=1", ksun_pin["repository"], ksun_pin["commit"])
        git(ksun, "checkout", "-q", "--detach", "FETCH_HEAD")
        expect("KSUN checkout", git(ksun, "rev-parse", "HEAD"), ksun_pin["commit"])

        replay(kernel, BASE / "replay/kernel-replay.json", kernel_commit)
        replay(ksun, BASE / "replay/ksun-replay.json", ksun_pin["commit"])
        head = snapshot(kernel)
        snapshot(ksun)
        excluded = []
        if not bbg:
            excluded += ["001-bbg.patch", "003-bbg-allow-cache-spinlock.patch"]
        if not networking:
            excluded += ["004-bbrv3.patch", "005-bbr3-alias.patch"]
        replay(kernel, BASE / "features/kernel-replay.json", head, excluded)

        if not gkid_parity.has_stack((kernel / gkid_parity.VERSION_C).read_text(errors="replace")):
            removed = gkid_parity.apply(kernel)
            print(f"[+] GKID-equivalent stack applied; removed {', '.join(removed)}")
        git(kernel, "add", "-A")
        print(f"[+] final source tree: {git(kernel, 'write-tree')}")
        print(f"SOURCE STAGED: KSUN + built-in SUSFS 6.1.{sublevel}; NoMount; "
              f"BBG={str(bbg).lower()}; Networking={str(networking).lower()}")
        return 0
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc)[:2000], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
