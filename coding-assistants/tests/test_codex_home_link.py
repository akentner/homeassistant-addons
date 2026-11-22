"""run.sh must route /root/.codex to CODEX_HOME so Codex started without CODEX_HOME keeps its state."""

from pathlib import Path
import subprocess
import tempfile
import unittest

RUN_SH = Path(__file__).resolve().parents[1] / "run.sh"
START = "if [[ -d /root/.codex && ! -L /root/.codex ]]; then"
END = 'ln -s "${CODEX_HOME}" /root/.codex\n'


def link_block() -> str:
    text = RUN_SH.read_text()
    return text[text.index(START):text.index(END) + len(END)]


class CodexHomeLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data/.codex").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_block(self):
        script = (
            "bashio::log.warning() { :; }\n"
            f'CODEX_HOME="{self.root}/data/.codex"\n'
            + link_block().replace("/root/.codex", f"{self.root}/root/.codex")
        )
        (self.root / "root").mkdir(exist_ok=True)
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_block_is_present_in_run_sh(self):
        self.assertIn(START, RUN_SH.read_text())

    def test_missing_root_codex_becomes_symlink(self):
        result = self.run_block()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.root / "root/.codex"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.root / "data/.codex").resolve())

    def test_real_directory_is_merged_without_overwriting(self):
        (self.root / "root/.codex").mkdir(parents=True)
        (self.root / "root/.codex/auth.json").write_text("new")
        (self.root / "root/.codex/extra").write_text("x")
        (self.root / "data/.codex/auth.json").write_text("old")
        result = self.run_block()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "root/.codex").is_symlink())
        self.assertEqual((self.root / "data/.codex/auth.json").read_text(), "old")
        self.assertEqual((self.root / "data/.codex/extra").read_text(), "x")

    def test_second_run_keeps_symlink(self):
        self.run_block()
        result = self.run_block()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "root/.codex").is_symlink())


if __name__ == "__main__":
    unittest.main()
