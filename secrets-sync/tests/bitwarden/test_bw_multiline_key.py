"""Pin how a multi-line private key travels from a Bitwarden item to secrets.yaml.

The path under test is: fake `bw` CLI -> Provider.fetch() -> Snapshot -> writer.render_secrets -> YAML parser.
The key used here is fake: it is generated at runtime from a seeded RNG and never read from disk.
"""

from __future__ import annotations

import base64
import random

import yaml

from app.engine.writer import render_secrets
from app.providers.bitwarden import Provider

# The marker label lives in a constant so no literal key header exists in this source file
LABEL = "OPENSSH PRIVATE KEY"


def fake_private_key(seed: str = "fake-key") -> str:
    """PEM-style fake key: 70-char base64 lines, short last line, exactly one trailing newline."""
    body = base64.b64encode(random.Random(seed).randbytes(400)).decode()
    lines = [body[i:i + 70] for i in range(0, len(body), 70)]
    return "\n".join([f"-----BEGIN {LABEL}-----", *lines, f"-----END {LABEL}-----"]) + "\n"


KEY = fake_private_key()


def test_fake_key_is_multiline_wrapped_with_trailing_newline():
    assert KEY.startswith("-----BEGIN ")
    assert KEY.endswith("-----\n")
    body = KEY.split("\n")[1:-2]
    assert len(body) > 5
    assert all(len(line) <= 70 for line in body)
    assert len(body[0]) == 70
    assert 0 < len(body[-1]) < 70


def test_login_notes_key_roundtrips_fetch_to_yaml(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 1, "name": "Deploy Host", "notes": KEY}])
    snap = Provider(bw_cfg).fetch()
    assert snap.secrets == {"deploy_host_notes": KEY}
    assert snap.files == {}
    text = render_secrets(snap.secrets)
    loaded = yaml.safe_load(text)
    assert loaded == snap.secrets
    assert loaded["deploy_host_notes"] == KEY
    assert loaded["deploy_host_notes"].endswith("\n")
    # header line plus exactly one physical line per key: the value is stored escaped on a single line
    assert text.count("\n") == 1 + len(snap.secrets)
