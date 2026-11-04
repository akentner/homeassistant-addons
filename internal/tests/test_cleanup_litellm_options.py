"""Exercise safeguards and protected backups without accessing a real Supervisor."""

import importlib.util
import json
import contextlib
import copy
import http.server
import io
import os
import threading
from unittest.mock import patch
from pathlib import Path
import stat
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("cleanup", Path(__file__).resolve().parents[1] / "cleanup-litellm-options.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def fixture():
    return {"version": "1.108.0-0", "state": "stopped", "options": {
        "env": {"litellm": [{"name": "API_KEY", "value": "!secret preserved_reference"}]},
        "models": [{"model": "old"}], "providers": {},
    }, "schema": [{"name": "env"}]}


class CleanupTests(unittest.TestCase):
    def test_only_obsolete_fields_are_removed_and_secret_references_preserved(self):
        info = fixture()
        removed, options = cleanup.plan_options(info)
        self.assertEqual(removed, ["models", "providers"])
        self.assertEqual(options, {"env": info["options"]["env"]})
        self.assertIn("models", info["options"])
        self.assertEqual(cleanup.plan_options({**info, "options": options})[0], [])

    def test_refuses_running_unsupported_or_schema_supported_fields(self):
        for patch in [{"state": "started"}, {"version": "1.0.0-0"}, {"schema": []},
                      {"schema": [{"name": "env"}, {"name": "models"}]},
                      {"options": {"unexpected": True}}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                cleanup.plan_options({**fixture(), **patch})

    def test_apply_uses_addons_api_and_preserves_active_options(self):
        info = fixture()
        original = copy.deepcopy(info["options"])
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def respond(self, data):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"result": "ok", "data": data}).encode())

            def do_GET(self):
                requests.append(("GET", self.path))
                if self.path != "/addons/72a005f5_litellm/info":
                    self.send_error(404)
                    return
                self.respond(info)

            def do_POST(self):
                requests.append(("POST", self.path))
                if self.path != "/addons/72a005f5_litellm/options":
                    self.send_error(404)
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                info["options"] = body["options"]
                self.respond(None)

        with tempfile.TemporaryDirectory() as root:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            endpoint = f"http://127.0.0.1:{server.server_port}"
            output = io.StringIO()
            try:
                with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-placeholder"}), patch("sys.argv", [
                    "cleanup", "--apply", "--endpoint", endpoint, "--backup-dir", str(Path(root) / "backup"),
                ]), contextlib.redirect_stdout(output):
                    cleanup.main()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
            backups = list((Path(root) / "backup").glob("*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text()), original)
        self.assertEqual(info["options"], {"env": original["env"]})
        self.assertEqual(info["state"], "stopped")
        self.assertEqual(sum(method == "POST" for method, _path in requests), 1)
        self.assertNotIn("preserved_reference", output.getvalue())

    def test_backup_is_complete_private_and_cannot_overwrite_existing_backup(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "private"
            options = fixture()["options"]
            first = cleanup.backup_options(directory, options)
            second = cleanup.backup_options(directory, options)
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first.read_text()), options)
            self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            directory.chmod(0o755)
            with self.assertRaises(ValueError):
                cleanup.backup_options(directory, options)
