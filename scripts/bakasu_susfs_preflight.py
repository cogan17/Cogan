#!/usr/bin/env python3
"""Read the pinned BakaSU SUSFS guard before downloads or compilation.

This only checks upstream's suspension; passing is not compatibility evidence.
No upstream makefile is executed or changed.
"""
import argparse
import base64
import binascii
import hashlib
import re
import sys
from pathlib import Path

GUARD = "kernel/tools/susfs_compat.mk"
REPO = "Baka-SU/BakaSU"
SHA = re.compile(r"[0-9a-f]{40}")


def check_remote(commit, json_of):
    """Reject any Make error in the exact source's guard, without selecting older CI."""
    if not SHA.fullmatch(commit):
        raise ValueError("BakaSU SUSFS preflight requires a full source commit")
    blob = json_of(f"/repos/{REPO}/contents/{GUARD}?ref={commit}")
    if (not isinstance(blob, dict) or blob.get("type") != "file" or blob.get("encoding") != "base64"
            or not isinstance(blob.get("content"), str)):
        raise ValueError("BakaSU SUSFS guard is missing or unreadable")
    try:
        data = base64.b64decode("".join(blob["content"].split()), validate=True)
        text = data.decode("utf-8")
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        raise ValueError("BakaSU SUSFS guard is malformed") from exc
    identity = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if blob.get("sha") != identity:
        raise ValueError("BakaSU SUSFS guard blob identity mismatch")
    # Conservatively reject conditional errors too: a new conditional gate needs
    # review against the pinned SUSFS/kernel sources, not an assumed pass here.
    active = "\n".join(line.split("#", 1)[0] for line in text.splitlines()).replace("\\\n", "")
    error = re.search(r"\$[({]\s*error(?=[\s)}])(?:[ \t]+([^\n)}]*))?", active)
    if error:
        reason = (error.group(1) or "SUSFS build suspended").strip()[:200]
        raise ValueError(f"BakaSU+SUSFS blocked by upstream at {commit[:12]}: {reason}; "
                         "wait for an upstream compatibility update; the guard must remain unchanged")
    return {"commit": commit, "guard_blob": identity,
            "guard_sha256": hashlib.sha256(data).hexdigest(), "status": "NO_UPSTREAM_SUSPENSION"}


def main(argv=None):
    try:
        from .cogan_manual_update import LOCK, api_json, read_lock
    except ImportError:
        from cogan_manual_update import LOCK, api_json, read_lock
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", type=Path, default=LOCK)
    args = parser.parse_args(argv)
    try:
        commit = read_lock(args.lock.read_text(encoding="utf-8"))["BSU_COMMIT"]
        check_remote(commit, api_json)
    except (OSError, ValueError, KeyError) as exc:
        print(f"BLOCKED: BakaSU SUSFS preflight: {exc}", file=sys.stderr)
        return 1
    print(f"BakaSU SUSFS preflight: no upstream suspension at {commit[:12]}; "
          "compilation and compatibility checks are still required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
