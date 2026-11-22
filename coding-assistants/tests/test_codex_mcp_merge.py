"""codex-mcp-merge must add managed MCP tables to config.toml and leave everything else alone."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "codex-mcp-merge"


def run(config: Path, servers) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(config)],
        input=json.dumps(servers), capture_output=True, text=True,
    )


class CodexMcpMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "config.toml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_file_with_command_and_url_entries(self):
        result = run(self.config, {
            "foo": {"command": "npx", "args": ["-y", "foo"], "env": {"A": "b\"c"}},
            "remote": {"url": "https://x.example/mcp"},
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        data = tomllib.loads(self.config.read_text())["mcp_servers"]
        self.assertEqual(data["foo"], {"command": "npx", "args": ["-y", "foo"], "env": {"A": 'b"c'}})
        self.assertEqual(data["remote"], {"url": "https://x.example/mcp"})
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_existing_entries_and_user_settings_win(self):
        original = '# my notes\nmodel = "gpt-5"\n\n[mcp_servers.foo]\ncommand = "mine"\nargs = []\n'
        self.config.write_text(original)
        result = run(self.config, {"foo": {"command": "npx", "args": []}, "bar": {"command": "bar", "args": []}})
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.config.read_text()
        self.assertTrue(text.startswith(original))
        data = tomllib.loads(text)
        self.assertEqual(data["mcp_servers"]["foo"]["command"], "mine")
        self.assertEqual(data["mcp_servers"]["bar"]["command"], "bar")
        self.assertEqual(data["model"], "gpt-5")

    def test_idempotent_second_run_leaves_file_identical(self):
        servers = {"foo": {"command": "npx", "args": ["x"], "env": {"A": "b"}}}
        run(self.config, servers)
        first = self.config.read_text()
        self.assertEqual(run(self.config, servers).returncode, 0)
        self.assertEqual(self.config.read_text(), first)

    def test_broken_toml_is_left_untouched_and_secrets_not_printed(self):
        self.config.write_text("this is [not toml")
        result = run(self.config, {"foo": {"command": "x", "args": [], "env": {"TOKEN": "s3cret-value"}}})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.config.read_text(), "this is [not toml")
        self.assertNotIn("s3cret-value", result.stdout + result.stderr)
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["config.toml"])

    def test_invalid_input_fails_without_writing(self):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), str(self.config)],
                                input="not json", capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.config.exists())

    def test_unusual_names_are_quoted(self):
        result = run(self.config, {"my server.v2": {"command": "x", "args": [], "env": {"A.B": "1"}}})
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = tomllib.loads(self.config.read_text())["mcp_servers"]["my server.v2"]
        self.assertEqual(entry["env"], {"A.B": "1"})

    def test_preserves_mode_of_existing_file(self):
        self.config.write_text("")
        os.chmod(self.config, 0o640)
        run(self.config, {"foo": {"command": "x", "args": []}})
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)


class WiringTests(unittest.TestCase):
    ADDON = SCRIPT.parent

    def test_run_sh_merges_options_and_zigbee2mqtt_into_codex(self):
        run_sh = (self.ADDON / "run.sh").read_text()
        self.assertIn('codex_mcp_merge "${MCP_OBJ_CODEX}"', run_sh)
        self.assertIn('codex_mcp_merge "${Z2M_OBJ_CODEX}"', run_sh)

    def test_run_sh_merges_mariadb_connections_into_codex(self):
        run_sh = (self.ADDON / "run.sh").read_text()
        self.assertIn("CODEX_MARIADB_COUNT=$((CODEX_MARIADB_COUNT + 1))", run_sh)
        self.assertIn("{ command: $cmd, args: [], env: {} }", run_sh)

    def test_dockerfile_installs_the_helper(self):
        dockerfile = (self.ADDON / "Dockerfile").read_text()
        self.assertIn("codex-mcp-merge", dockerfile.split("# HA API tools", 1)[1].split("# Home Assistant CLI", 1)[0])
        self.assertTrue(os.access(SCRIPT, os.X_OK))


if __name__ == "__main__":
    unittest.main()
