import hashlib
import unittest
from pathlib import Path


class ReleaseManifestTests(unittest.TestCase):
    def test_entries_exist_and_match(self):
        repo = Path(__file__).resolve().parents[1]
        manifest = repo / "RELEASE_MANIFEST.sha256"
        entries = manifest.read_text(encoding="utf-8").splitlines()

        self.assertTrue(entries)
        for line in entries:
            expected, relative = line.split(maxsplit=1)
            relative = relative.removeprefix("./")
            self.assertNotIn(".pytest_cache", Path(relative).parts)
            target = repo / relative
            self.assertTrue(target.is_file(), f"manifest entry does not exist: {relative}")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(actual, expected, f"manifest hash mismatch: {relative}")


if __name__ == "__main__":
    unittest.main()
