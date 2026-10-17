#!/usr/bin/env python3
"""Regression coverage for build #21's upstream BakaSU/SUSFS suspension."""
import base64
import contextlib
import hashlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import bakasu_susfs_preflight as preflight
from scripts import cogan_manual_update as mu

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "2489b38582a08fee7b586d05185da5e5d12c6a5c"
SUSPENDED = b"""$(info -- $(REPO_NAME): susfs has NOT update with latest KernelSU source)
$(info -- $(REPO_NAME): Please wait simonpunk update)
$(error Please wait susfs update.)"""


def blob(data):
    return {"type": "file", "encoding": "base64", "content": base64.b64encode(data).decode(),
            "sha": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}


class BakaSusfsPreflightTests(unittest.TestCase):
    def test_upstream_suspension_is_reported_from_the_exact_commit(self):
        fetch = mock.Mock(return_value=blob(SUSPENDED))
        with self.assertRaisesRegex(ValueError, "blocked by upstream at 2489b38582a0: Please wait susfs update"):
            preflight.check_remote(COMMIT, fetch)
        fetch.assert_called_once_with(
            f"/repos/Baka-SU/BakaSU/contents/kernel/tools/susfs_compat.mk?ref={COMMIT}")

    def test_only_comments_are_ignored_and_new_conditional_errors_need_review(self):
        supported = b"# $(error historical suspension)\n$(info SUSFS hooks found)\n"
        result = preflight.check_remote(COMMIT, lambda path: blob(supported))
        self.assertEqual(result["status"], "NO_UPSTREAM_SUSPENSION")
        self.assertEqual(result["guard_sha256"], hashlib.sha256(supported).hexdigest())
        for data in (b"ifeq (x,y)\n$(error new compatibility gate)\nendif\n",
                     b"${error Please wait susfs update.}\n", b"$(error)\n"):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "blocked by upstream"):
                preflight.check_remote(COMMIT, lambda path: blob(data))

    def test_missing_malformed_or_changed_guard_never_passes(self):
        valid = blob(b"# SUSFS source fixture\n")
        for response in ({}, [], {**valid, "content": "%%%"}, {**valid, "sha": "0" * 40},
                         {**valid, "encoding": "utf-8"}, {**valid, "content": 123}, blob(b"\xff")):
            with self.subTest(response=response), self.assertRaises(ValueError):
                preflight.check_remote(COMMIT, lambda path: response)
        fetch = mock.Mock(side_effect=OSError("source unavailable"))
        with self.assertRaises(OSError):
            preflight.check_remote(COMMIT, fetch)
        for ref in ("main", "v4.2.0-rc3", "123"):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "full source commit"):
                preflight.check_remote(ref, fetch)

    def test_cli_uses_the_lock_and_fails_without_changing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstream.lock"
            original = mu.LOCK.read_bytes()
            path.write_bytes(original)
            output = Path(directory) / "step-output"
            for source, status in ((blob(SUSPENDED), "UPSTREAM_BLOCKED"), (None, "CHECK_FAILED")):
                stderr = io.StringIO()
                output.unlink(missing_ok=True)
                with mock.patch.object(mu, "api_json", return_value=source), \
                        mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), contextlib.redirect_stderr(stderr):
                    self.assertEqual(preflight.main(["--lock", str(path)]), 1)
                self.assertIn("BLOCKED", stderr.getvalue())
                self.assertEqual(path.read_bytes(), original)
                fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
                self.assertEqual(fields["bakasu_susfs_status"], status)
                self.assertEqual(fields["bakasu_susfs_reason"],
                                 "Please wait susfs update." if status == "UPSTREAM_BLOCKED" else "")

    def render_summary(self, outputs, manager="BSU", outcome="failure", susfs="true"):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
        step = next(s for s in workflow["jobs"]["build"]["steps"] if s["name"] == "Build result summary")
        # Resolve the actual workflow bindings so a missing/miswired output fails.
        context = {"steps.kernel-build.outcome": outcome,
                   "steps.kernel-build.outputs.bakasu_susfs_status": outputs.get("bakasu_susfs_status", ""),
                   "steps.kernel-build.outputs.bakasu_susfs_reason": outputs.get("bakasu_susfs_reason", ""),
                   "matrix.KSU": manager, "matrix.KSU_SUSFS": susfs,
                   "inputs.NETWORKING": "true", "inputs.BBG": "true"}
        env = {**os.environ, **{key: context[value.removeprefix("${{ ").removesuffix(" }}")]
                               for key, value in step["env"].items()}}
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            env["GITHUB_STEP_SUMMARY"] = str(summary)
            subprocess.run(["/bin/bash", "-e", "-u", "-o", "pipefail", "-c", step["run"]],
                           env=env, check=True, capture_output=True, text=True)
            return summary.read_text()

    def test_suspended_preflight_reaches_both_summary_languages(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "step-output"
            with mock.patch.object(mu, "api_json", return_value=blob(SUSPENDED)), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(preflight.main(["--github-output", str(output)]), 1)
            fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
        summary = self.render_summary(fields)
        self.assertEqual(summary.count("Root manager: BakaSU + SUSFS"), 2)
        self.assertEqual(summary.count("`Please wait susfs update.`"), 2)
        self.assertIn("**BakaSU + SUSFS ditahan upstream.**", summary)
        self.assertIn("**BakaSU + SUSFS suspended upstream.**", summary)
        self.assertIn("Kompilasi kernel tidak dijalankan", summary)
        self.assertIn("this job produced no new kernel ZIP", summary)
        self.assertIn("Hasil skrip build: failure", summary)
        self.assertNotIn("**Build gagal.**", summary)
        self.assertNotIn("KernelSU Next", summary)

    def test_other_failures_and_success_are_not_reported_as_upstream_suspensions(self):
        for manager, outcome, status, susfs in (
                ("BSU", "failure", "CHECK_FAILED", "true"),
                ("BSU", "failure", "", "true"),
                ("KSUN", "failure", "UPSTREAM_BLOCKED", "true"),
                ("BSU", "success", "NO_UPSTREAM_SUSPENSION", "true"),
                ("no", "success", "", "false")):
            with self.subTest(manager=manager, outcome=outcome, status=status):
                summary = self.render_summary({"bakasu_susfs_status": status}, manager, outcome, susfs)
                self.assertNotIn("ditahan upstream", summary)
                self.assertNotIn("suspended upstream", summary)
                self.assertNotIn("Please wait", summary)
                if outcome == "failure":
                    self.assertIn("**Build gagal.**", summary)
                    self.assertIn("**Build failed.**", summary)
                else:
                    self.assertIn("**Skrip build berhasil.**", summary)
                    self.assertIn("**Build script succeeded.**", summary)
                if manager == "KSUN":
                    self.assertIn("Root manager: KernelSU Next + SUSFS", summary)
                if manager == "no":
                    self.assertIn("Root manager: Vanilla", summary)

    def test_build_stops_before_tools_downloads_or_workspace_changes(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as commands:
            python = Path(commands) / "python3"
            python.write_text("#!/bin/bash\n"
                              f'[[ "$1" == "{ROOT}/scripts/bakasu_susfs_preflight.py" ]] || exit 75\n'
                              'echo "BLOCKED: BakaSU+SUSFS blocked by upstream" >&2\nexit 1\n')
            python.chmod(0o755)
            env = {**os.environ, "PATH": commands, "KSU": "BSU", "KSU_SUSFS": "true",
                   "KERNEL_SUBLEVEL": "177"}
            result = subprocess.run(["/bin/bash", str(ROOT / "build.sh")], cwd=directory,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("blocked by upstream", result.stderr)
            self.assertNotIn("command not found", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
