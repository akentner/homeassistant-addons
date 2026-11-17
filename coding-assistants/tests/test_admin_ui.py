"""Check the shipped entry pages and real nginx static routes without Docker or third-party packages."""

import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ADDON = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.violations = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if any(key.startswith("on") or key == "style" for key in attrs):
            self.violations.append(tag)
        if tag == "script":
            if not attrs.get("src"):
                self.violations.append("inline script")
            else:
                self.paths.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.paths.append(attrs["href"])


class EntryTests(unittest.TestCase):
    def test_entries_use_shared_external_assets(self):
        for name in ("index.html", "info.html"):
            with self.subTest(name=name):
                parser = Assets()
                parser.feed((ADDON / name).read_text())
                self.assertFalse(parser.violations)
                self.assertIn("static/vendor/admin-ui/base.css", parser.paths)
                self.assertIn("static/app.mjs", parser.paths)
                for path in parser.paths:
                    self.assertFalse(path.startswith("/"))
                    self.assertTrue((ADDON / "app/web" / path).is_file())


@unittest.skipUnless(shutil.which("nginx"), "nginx is not installed")
class NginxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory()
        cls.root = Path(cls.scratch.name)
        cls.root.chmod(0o755)
        for name in ("index.html", "info.html", "icon.png"):
            (cls.root / name).symlink_to(ADDON / name)
        (cls.root / "static").symlink_to(ADDON / "app/web/static")
        cls.versions = {"addon": "1.3.1-0", "codex": "0.167.0"}
        (cls.root / "versions.json").write_text(json.dumps(cls.versions))
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        config = (ADDON / "nginx.conf").read_text()
        config = config.replace("listen 8099;", f"listen 127.0.0.1:{port};")
        config = config.replace("/opt/coding-assistants", str(cls.root))
        config = config.replace("/tmp/nginx.pid", str(cls.root / "nginx.pid"))
        config_path = cls.root / "nginx.conf"
        config_path.write_text(config)
        cls.process = subprocess.Popen(
            [shutil.which("nginx"), "-p", str(cls.root), "-c", str(config_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        cls.base = f"http://127.0.0.1:{port}/"
        for _ in range(100):
            if cls.process.poll() is not None:
                raise RuntimeError(cls.process.stderr.read().decode())
            try:
                cls.fetch("")
                return
            except URLError:
                time.sleep(0.05)
        cls.process.terminate()
        cls.process.communicate(timeout=5)
        raise RuntimeError("test nginx did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.communicate(timeout=5)
        cls.scratch.cleanup()

    @classmethod
    def fetch(cls, path):
        request = Request(urljoin(cls.base, path), headers={"X-Ingress-Path": "/api/hassio_ingress/test"})
        with urlopen(request, timeout=2) as response:
            return response.read(), response.headers.get_content_type()

    def test_entire_module_graph_loads_below_ingress_with_javascript_mime(self):
        body, _ = self.fetch("")
        parser = Assets()
        parser.feed(body.decode())
        prefix = "/api/hassio_ingress/test/"
        pending = [urljoin(prefix, path) for path in parser.paths]
        seen = set()
        while pending:
            external_path = pending.pop()
            if external_path in seen:
                continue
            self.assertTrue(external_path.startswith(prefix), external_path)
            seen.add(external_path)
            body, mime = self.fetch(external_path[len(prefix):])
            if external_path.endswith(".mjs"):
                self.assertEqual(mime, "application/javascript", external_path)
                for match in re.finditer(r"\b(?:from\s*|import\s*)[\"'](\.[^\"']+)[\"']", body.decode()):
                    pending.append(urljoin(external_path, match[1]))
        self.assertGreater(len(seen), 12)

    def test_relative_versions_endpoint(self):
        body, mime = self.fetch("api/versions")
        self.assertEqual(mime, "application/json")
        self.assertEqual(json.loads(body), self.versions)

    def test_library_metadata_is_not_served(self):
        for path in ("static/vendor/admin-ui/LIB.stamp", "static/vendor/admin-ui/VERSION", "static/vendor/admin-ui/__pycache__/x.pyc"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.fetch(path)
            self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
