"""Pin how a multi-line private key travels from a Bitwarden item to secrets.yaml.

The path under test is: fake `bw` CLI -> Provider.fetch() -> Snapshot -> writer.render_secrets -> YAML parser.
The key used here is fake: it is generated at runtime from a seeded RNG and never read from disk.

Findings (documented by the tests below):

1. A private key kept in a Login item's notes or in a Login custom field is exported as the secret
   `<item>_notes` / `<item>_<field>`, byte-identical (newlines and trailing newline included), and stored escaped
   on a single physical YAML line.
2. A Secure Note (type 2) is exported as a file below `notes_dir`, never as a secret.
3. SSH-key items (type 5) are not exported at all, and the `item_skipped` notice counts them under the wording
   "card/identity items skipped".
"""

from __future__ import annotations

import base64
import random

import yaml

from app.engine.writer import read_secrets, render_secrets, write_secrets
from app.providers.bitwarden import Provider

# The marker label lives in a constant so no literal key header exists in this source file
LABEL = "OPENSSH PRIVATE KEY"


def fake_private_key(seed: str = "fake-key") -> str:
    """PEM-style fake key: 70-char base64 lines, short last line, exactly one trailing newline."""
    body = base64.b64encode(random.Random(seed).randbytes(400)).decode()
    lines = [body[i:i + 70] for i in range(0, len(body), 70)]
    return "\n".join([f"-----BEGIN {LABEL}-----", *lines, f"-----END {LABEL}-----"]) + "\n"


KEY = fake_private_key()
# A different fake key, so a cross-wired value would be detected
FIELD_KEY = fake_private_key("field-key")


def _deploy_host_item() -> dict:
    return {"type": 1, "name": "Deploy Host", "notes": KEY,
            "fields": [{"name": "Private Key", "value": FIELD_KEY, "type": 1}]}


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


def test_login_custom_field_key_roundtrips_next_to_notes(fake_bw, bw_cfg):
    fake_bw.set_items([_deploy_host_item()])
    snap = Provider(bw_cfg).fetch()
    assert snap.secrets == {"deploy_host_notes": KEY, "deploy_host_private_key": FIELD_KEY}
    assert KEY != FIELD_KEY
    assert all(value.endswith("\n") for value in snap.secrets.values())
    text = render_secrets(snap.secrets)
    loaded = yaml.safe_load(text)
    assert loaded == snap.secrets
    assert loaded["deploy_host_notes"] == KEY
    assert loaded["deploy_host_private_key"] == FIELD_KEY
    assert text.count("\n") == 1 + len(snap.secrets)


def test_write_secrets_then_read_secrets_keeps_keys_byte_identical(fake_bw, bw_cfg, tmp_path):
    fake_bw.set_items([_deploy_host_item()])
    snap = Provider(bw_cfg).fetch()
    target = tmp_path / "cfg" / "secrets.yaml"
    assert write_secrets(target, snap.secrets) is True
    assert yaml.safe_load(target.read_text(encoding="utf-8")) == snap.secrets
    assert read_secrets(target) == snap.secrets
    assert target.read_bytes() == render_secrets(snap.secrets).encode("utf-8")
    # byte-identical content: nothing is rewritten
    assert write_secrets(target, snap.secrets) is False


def test_secure_note_key_becomes_file_not_secret(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 2, "name": "Deploy Key", "notes": KEY}])
    provider = Provider(bw_cfg)
    snap = provider.fetch()
    assert snap.files == {"bitwarden/deploy_key.txt": KEY.encode("utf-8")}
    assert snap.secrets == {}
    assert provider.notices == []


# `_build` handles item types 1 and 2 only, so type 5 (sshKey) falls into the generic skipped counter and the
# notice therefore counts an SSH-key item as a "card/identity" item. The wording is production behaviour that is
# deliberately left unchanged here (test-only task); update this assertion on purpose when the wording is fixed.
def test_ssh_key_item_type5_is_skipped_and_counted_as_card_identity(fake_bw, bw_cfg):
    fake_bw.set_items([
        {"type": 1, "name": "Deploy Host", "login": {"username": "git"}},
        {"type": 5, "name": "Deploy SSH",
         "sshKey": {"privateKey": KEY, "publicKey": "ssh-ed25519 AAAAfakepublickey", "keyFingerprint": "SHA256:fake"}},
    ])
    provider = Provider(bw_cfg)
    snap = provider.fetch()
    assert snap.secrets == {"deploy_host_username": "git"}
    assert snap.files == {}
    assert KEY not in snap.secrets.values()
    assert not any(name.startswith("deploy_ssh") for name in (*snap.secrets, *snap.files))
    assert provider.notices == [("info", "item_skipped", "1 card/identity items skipped")]
    assert KEY.split("\n")[1] not in repr(provider.notices)
