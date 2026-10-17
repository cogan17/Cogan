import unittest

from apk_fixture import apk_bytes
from scripts.apk_identity import apk_identity, verify_bakasu_apk


class ApkIdentityTests(unittest.TestCase):
    def test_reads_real_label_resource_and_allows_a_random_spoofed_package(self):
        for utf8 in (True, False):
            for flags in (0, 1, 2):
                with self.subTest(utf8=utf8, flags=flags):
                    identity = verify_bakasu_apk(apk_bytes(package="random.manager.id", utf8=utf8,
                                                         entry_flags=flags))
                    self.assertEqual(identity["package"], "random.manager.id")
                    self.assertEqual(identity["labels"], ["BakaSU"])
                    self.assertEqual(identity["versionCode"], 35231)

    def test_rejects_resukisu_even_if_the_download_is_named_bakasu(self):
        with self.assertRaisesRegex(ValueError, "embedded application label.*ReSukiSU"):
            verify_bakasu_apk(apk_bytes(label="ReSukiSU"))

    def test_direct_manifest_label_is_read(self):
        self.assertEqual(apk_identity(apk_bytes(resource=False))["labels"], ["BakaSU"])

    def test_damaged_metadata_fails_closed(self):
        with self.assertRaises(ValueError):
            verify_bakasu_apk(b"not an APK")


if __name__ == "__main__":
    unittest.main()
