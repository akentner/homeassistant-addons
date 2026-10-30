"""Pin how a multi-line private key travels from a Bitwarden item to secrets.yaml.

The path under test is: fake `bw` CLI -> Provider.fetch() -> Snapshot -> writer.render_secrets -> YAML parser.
The key used here is fake: it is generated at runtime from a seeded RNG and never read from disk.

Findings (documented by the tests below):

1. A private key kept in a Login item's notes or in a Login custom field is exported as the secret
   `<item>_notes` / `<item>_<field>`, byte-identical (newlines and trailing newline included), and stored escaped
   on a single physical YAML line.
2. A Secure Note (type 2) is exported as a file below `notes_dir`, never as a secret.
3. SSH-key items (type 5) export `<item>_private_key` and `<item>_public_key`; a custom field `secrets_sync` =
   `public` limits the export to the public key.
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


PUB = "ssh-ed25519 AAAAfakepublickey"


def _ssh_item(**extra):
    return {"type": 5, "name": "Deploy SSH",
            "sshKey": {"privateKey": KEY, "publicKey": PUB, "keyFingerprint": "SHA256:fake"}, **extra}


def test_ssh_key_item_type5_exports_private_and_public_key(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 1, "name": "Deploy Host", "login": {"username": "git"}}, _ssh_item()])
    provider = Provider(bw_cfg)
    snap = provider.fetch()
    assert snap.secrets == {"deploy_host_username": "git", "deploy_ssh_private_key": KEY,
                            "deploy_ssh_public_key": PUB}
    assert snap.files == {}
    assert provider.notices == []  # no fingerprint key, nothing skipped


def test_ssh_key_item_marked_public_exports_only_public_key(fake_bw, bw_cfg):
    marker = {"fields": [{"name": "Secrets_Sync", "value": " Public ", "type": 0}]}
    fake_bw.set_items([_ssh_item(**marker)])
    snap = Provider(bw_cfg).fetch()
    assert snap.secrets == {"deploy_ssh_public_key": PUB}
    assert KEY not in snap.secrets.values()


def test_other_marker_value_keeps_private_key(fake_bw, bw_cfg):
    fake_bw.set_items([_ssh_item(fields=[{"name": "secrets_sync", "value": "all", "type": 0}])])
    assert "deploy_ssh_private_key" in Provider(bw_cfg).fetch().secrets


def test_card_and_identity_are_still_skipped_with_notice(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 3, "name": "card"}, {"type": 4, "name": "id"}, _ssh_item()])
    provider = Provider(bw_cfg)
    snap = provider.fetch()
    assert set(snap.secrets) == {"deploy_ssh_private_key", "deploy_ssh_public_key"}
    assert provider.notices == [("info", "item_skipped", "2 card/identity items skipped")]
