#!/usr/bin/env python3
"""Current feature selections must reach the source tree and resolved config."""
import contextlib
import hashlib
import io
import itertools
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_ksun_susfs_resolved_config as audit
from scripts import ksun_susfs_config as config
from scripts import stage_ksun_susfs_candidate as stage

ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = 'CONFIG_LSM="landlock,lockdown,yama,integrity,selinux,bpf"\n'


class ConfigOptionsTests(unittest.TestCase):
    def test_build_fragment_covers_all_feature_combinations(self):
        for lto, bbg, networking in itertools.product(config.LTO_SYMBOLS, ("false", "true"), ("false", "true")):
            with self.subTest(lto=lto, bbg=bbg, networking=networking):
                fragment = config.fragment(BASE_CONFIG, lto, bbg, networking).encode()
                values = audit.parse_config(fragment)
                self.assertEqual(values["CONFIG_KSU_SUSFS"], "y")
                self.assertEqual(values["CONFIG_NOMOUNT"], "y")
                self.assertEqual(values["CONFIG_KSU_SAMSUNG_KDP"], "n")
                self.assertEqual(values["CONFIG_BBG"], "y" if bbg == "true" else "n")
                self.assertEqual("baseband_guard" in values["CONFIG_LSM"], bbg == "true")
                self.assertIn("selinux", values["CONFIG_LSM"])
                self.assertEqual(values.get("CONFIG_DEFAULT_BBR"), "y" if networking == "true" else None)
                expected = config.LTO_SYMBOLS[lto]
                self.assertEqual([key for key in config.LTO_SYMBOLS.values() if values[key] == "y"], [expected])
                spec = {"configuration": {"required": values, "forbidden": []}}
                self.assertEqual(audit.audit(fragment, spec), [])
                wrong = fragment.replace(f"{expected}=y".encode(), f"{expected}=n".encode())
                self.assertTrue(any(expected in error for error in audit.audit(wrong, spec)))
                wrong = fragment.replace(b"CONFIG_NOMOUNT=y", b"CONFIG_NOMOUNT=n")
                self.assertTrue(any("CONFIG_NOMOUNT" in error for error in audit.audit(wrong, spec)))

    def test_standard_variants_explicitly_set_every_lto_choice(self):
        for mode, expected in config.LTO_SYMBOLS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                dest = root / "arch/arm64/configs/gki_defconfig"
                dest.parent.mkdir(parents=True)
                dest.write_text("")
                env = {**os.environ, "WORKDIR": str(ROOT), "KSU": "KSUN", "KSU_SUSFS": "false",
                       "KSU_COMPAT": "false", "C_LTO": "true", "LTO": mode, "NETWORKING": "false", "BBG": "false",
                       "DROIDSPACES": "false", "NH": "false", "No_DS": "true"}
                result = subprocess.run(["bash", str(ROOT / "configs/gki_defconfig.sh")], cwd=root,
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = dest.read_text()
                self.assertIn(f"{expected}=y\n", text)
                self.assertGreater(text.rfind("CONFIG_BBG=n"), text.rfind("CONFIG_BBG=y"))
                for key in config.LTO_SYMBOLS.values():
                    if key != expected:
                        self.assertIn(f"{key}=n\n", text)

    def test_invalid_requests_or_missing_selinux_are_rejected(self):
        for args in (("bad", "true", "true"), ("noneLTO", "bad", "true"), ("noneLTO", "true", "bad")):
            with self.assertRaises(ValueError):
                config.fragment(BASE_CONFIG, *args)
        with self.assertRaisesRegex(ValueError, "selinux"):
            config.fragment('CONFIG_LSM="landlock"\n', "noneLTO", "false", "false")


class StageOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kernel, self.ksun = self.root / "kernel", self.root / "ksun"
        self.upstream = self.root / "ksun-upstream"
        self.kernel.mkdir()
        (self.kernel / "kernel/module").mkdir(parents=True)
        (self.kernel / "kernel/module/version.c").write_text('pr_warn("disagrees about version of symbol, but ignore...");\n')
        (self.kernel / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 1\nSUBLEVEL = 178\n")
        self.upstream.mkdir()
        (self.upstream / "version.txt").write_text("pinned\n")
        self.kernel_pin, self.ksun_pin = self.init(self.kernel), self.init(self.upstream)
        self.base = self.root / "patches"
        (self.base / "replay").mkdir(parents=True)
        (self.base / "features").mkdir()
        self.manifest(self.base / "replay/kernel-replay.json", "0" * 40,
                      [("core.patch", "susfs.txt", None, "built-in\n")])
        self.manifest(self.base / "replay/ksun-replay.json", self.ksun_pin,
                      [("version.patch", "version.txt", "pinned\n", "offline\n")])
        self.manifest(self.base / "features/kernel-replay.json", "0" * 40, [
            ("001-bbg.patch", "bbg.txt", None, "bbg\n"),
            ("002-nomount.patch", "nomount.txt", None, "nomount\n"),
            ("003-bbg-allow-cache-spinlock.patch", "bbg.txt", "bbg\n", "bbg locking fix\n"),
            ("004-bbrv3.patch", "bbr.txt", None, "bbrv3\n"),
            ("005-bbr3-alias.patch", "bbr.txt", "bbrv3\n", "bbrv3 bbr3\n")])
        source_lock = self.root / "source.json"
        source_lock.write_text(json.dumps({"sources": {"ksun": {
            "repository": str(self.upstream), "commit": self.ksun_pin}}}))
        pins = self.root / "upstream.lock"
        pins.write_text(f"KERNEL_COMMIT_6_1={self.kernel_pin}\nKERNEL_COMMIT_6_1_178={self.kernel_pin}\n")
        for target, name, value in ((stage, "BASE", self.base), (stage, "SOURCE_LOCK", source_lock),
                                    (stage.sublevels, "UPSTREAM_LOCK", pins)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def init(self, repo):
        stage.git(repo, "init", "-q")
        stage.git(repo, "add", "-A")
        stage.git(repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-qm", "base")
        return stage.git(repo, "rev-parse", "HEAD")

    def manifest(self, path, pin, entries):
        patches = []
        for name, target, before, after in entries:
            header = f"diff --git a/{target} b/{target}\n"
            if before is None:
                raw = header + f"new file mode 100644\n--- /dev/null\n+++ b/{target}\n@@ -0,0 +1 @@\n+{after}"
            else:
                raw = header + f"--- a/{target}\n+++ b/{target}\n@@ -1 +1 @@\n-{before}+{after}"
            (path.parent / name).write_text(raw)
            patches.append({"path": name, "sha256": hashlib.sha256(raw.encode()).hexdigest()})
        path.write_text(json.dumps({"kernel_commit": pin, "patches": patches}))

    def test_stage_follows_each_checkbox_without_recorded_sublevel_or_tree_ids(self):
        for bbg, networking in itertools.product(("false", "true"), repeat=2):
            with self.subTest(bbg=bbg, networking=networking):
                stage.git(self.kernel, "reset", "--hard", self.kernel_pin)
                if self.ksun.exists():
                    import shutil
                    shutil.rmtree(self.ksun)
                with mock.patch.dict(os.environ, BBG=bbg, NETWORKING=networking), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(stage.main(["stage", str(self.kernel), str(self.ksun), "lts"]), 0)
                self.assertEqual((self.kernel / "susfs.txt").read_text(), "built-in\n")
                self.assertEqual((self.kernel / "nomount.txt").read_text(), "nomount\n")
                self.assertEqual((self.kernel / "bbg.txt").exists(), bbg == "true")
                self.assertEqual((self.kernel / "bbr.txt").exists(), networking == "true")
                if bbg == "true":
                    self.assertEqual((self.kernel / "bbg.txt").read_text(), "bbg locking fix\n")
                if networking == "true":
                    self.assertEqual((self.kernel / "bbr.txt").read_text(), "bbrv3 bbr3\n")
                self.assertEqual((self.ksun / "version.txt").read_text(), "offline\n")

    def test_wrong_source_pin_still_fails_before_fetch(self):
        (self.kernel / "extra").write_text("new\n")
        stage.git(self.kernel, "add", "extra")
        stage.git(self.kernel, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-qm", "moved")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(stage.main(["stage", str(self.kernel), str(self.ksun), "lts"]), 1)
        self.assertFalse(self.ksun.exists())


if __name__ == "__main__":
    unittest.main()
