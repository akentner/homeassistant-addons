"""The local build must resolve exactly the same versions and base image as the CI pipeline."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"


@unittest.skipUnless(shutil.which("make") and shutil.which("git"), "make and git are required")
class BuildMetadataTests(unittest.TestCase):
    def test_multiple_tool_versions_do_not_pollute_image_version(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            addon = root / "fixture"
            addon.mkdir()
            (addon / "build.yaml").write_text(
                'build_from:\n  # amd64: "wrong-image"\n  amd64: "example/base:stable"\n'
                'args:\n  VERSION: "1.2.3"\n  OPENCODE_VERSION: "2.2.6"\n'
                '  CODEX_VERSION: "0.167.0"\n  HERDR_VERSION: "0.9.3"\n'
            )
            (addon / "config.yaml").write_text('version: "1.2.3-4"\n')
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "remote", "add", "origin", "https://github.com/example/repo"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "fixture"], check=True,
            )
            result = subprocess.run(
                ["make", "-n", "-f", str(MAKEFILE), "build-addon", "ADDON=fixture"],
                cwd=root, capture_output=True, text=True, check=True,
            )
            self.assertIn('--build-arg VERSION="1.2.3"', result.stdout)
            self.assertIn('--build-arg BUILD_VERSION="1.2.3-4"', result.stdout)
            self.assertIn('--build-arg BUILD_FROM="example/base:stable"', result.stdout)
            self.assertIn('-t "local/fixture:1.2.3-4"', result.stdout)
            self.assertNotIn("2.2.6", result.stdout)
            self.assertNotIn("wrong-image", result.stdout)
