import logging
import os
import shutil

import pytest

from app.providers.base import ProviderError
from app.providers.sops import Provider

pytestmark = pytest.mark.skipif(
    not (shutil.which("sops") and shutil.which("age-keygen")), reason="sops and age-keygen are not installed"
)

PLAIN = """\
api_key: s3cr3t-value-ONE
port: 8123
debug: true
db:
  user: admin
  pass: s3cr3t-value-TWO
  deep:
    token: s3cr3t-value-THREE
"""


def make(path, key, sep="_"):
    return Provider({"file": str(path), "flatten_separator": sep, "age_key_file": str(key)})


def test_fetch_flattens(encrypt, age_key):
    snap = make(encrypt(PLAIN), age_key[0]).fetch()
    assert snap.secrets == {
        "api_key": "s3cr3t-value-ONE",
        "port": "8123",
        "debug": "true",
        "db_user": "admin",
        "db_pass": "s3cr3t-value-TWO",
        "db_deep_token": "s3cr3t-value-THREE",
    }
    assert snap.revision.isdigit()
    assert snap.files == {}


def test_custom_separator(encrypt, age_key):
    snap = make(encrypt(PLAIN), age_key[0], sep=".").fetch()
    assert "db.deep.token" in snap.secrets


def test_env_key_file(encrypt, age_key, monkeypatch):
    monkeypatch.setenv("SS_AGE_KEY_FILE", str(age_key[0]))
    assert Provider({"file": str(encrypt(PLAIN))}).fetch().secrets["port"] == "8123"


def test_key_permissions(encrypt, age_key):
    path = encrypt(PLAIN)
    age_key[0].chmod(0o644)
    with pytest.raises(ProviderError) as e:
        make(path, age_key[0]).fetch()
    assert e.value.code == "sops_key_permissions"
    age_key[0].chmod(0o400)
    assert make(path, age_key[0]).fetch().secrets


def test_key_missing_and_not_regular(encrypt, age_key, tmp_path):
    path = encrypt(PLAIN)
    with pytest.raises(ProviderError) as e:
        make(path, tmp_path / "nope").fetch()
    assert e.value.code == "sops_key_missing"
    with pytest.raises(ProviderError) as e:
        make(path, tmp_path).fetch()
    assert e.value.code == "sops_key_missing"


def test_file_missing(age_key, tmp_path):
    with pytest.raises(ProviderError) as e:
        make(tmp_path / "none.yaml", age_key[0]).fetch()
    assert e.value.code == "sops_file_missing"


def test_plaintext_rejected(age_key, tmp_path):
    f = tmp_path / "plain.yaml"
    f.write_text(PLAIN)
    with pytest.raises(ProviderError) as e:
        make(f, age_key[0]).fetch()
    assert e.value.code == "sops_not_encrypted"
    assert "s3cr3t" not in str(e.value)


def test_decrypt_failure_with_other_key(encrypt, age_key, tmp_path):
    import subprocess

    path = encrypt(PLAIN)
    other = tmp_path / "other.key"
    subprocess.run(["age-keygen", "-o", str(other)], check=True, capture_output=True)
    other.chmod(0o600)
    with pytest.raises(ProviderError) as e:
        make(path, other).fetch()
    assert e.value.code == "sops_decrypt_failed"


@pytest.mark.parametrize("plain", ["items:\n  - s3cr3t-list-value\n", "nothing: null\n"])
def test_unsupported_values_name_keys_only(encrypt, age_key, plain):
    with pytest.raises(ProviderError) as e:
        make(encrypt(plain), age_key[0]).fetch()
    assert e.value.code == "sops_unsupported_value"
    assert "s3cr3t" not in str(e.value)
    assert ("items" in str(e.value)) or ("nothing" in str(e.value))


def test_flatten_collision(encrypt, age_key):
    with pytest.raises(ProviderError) as e:
        make(encrypt("a_b: x-secret\na:\n  b: y-secret\n"), age_key[0]).fetch()
    assert e.value.code == "key_collision"
    assert "secret" not in str(e.value)


def test_validate():
    assert Provider({"file": "/x", "flatten_separator": "_"}).validate({}) == []
    codes = {p.code for p in Provider({"file": " ", "flatten_separator": ""}).validate({})}
    assert codes == {"sops_missing_file", "sops_empty_separator"}


def test_no_leak_no_tempfiles(encrypt, age_key, tmp_path, caplog, monkeypatch):
    path = encrypt(PLAIN)
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    for var in ("TMPDIR", "TMP", "TEMP"):
        monkeypatch.setenv(var, str(tmpdir))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    before = sorted(p.name for p in tmp_path.iterdir())
    caplog.set_level(logging.DEBUG)
    snap = make(path, age_key[0]).fetch()
    assert snap.secrets
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert list(tmpdir.iterdir()) == []
    assert not any("s3cr3t" in r.getMessage() for r in caplog.records)

    # failure path: wrong key, exception text must be clean
    other = tmp_path / "o.key"
    other.write_text(age_key[0].read_text().replace("AGE-SECRET-KEY-", "AGE-SECRET-KEY-"))
    other.chmod(0o600)
    os.environ.pop("SOPS_AGE_KEY_FILE", None)
    bad = tmp_path / "bad.key"
    bad.write_text("garbage s3cr3t-value-ONE\n")
    bad.chmod(0o600)
    with pytest.raises(ProviderError) as e:
        make(path, bad).fetch()
    assert "s3cr3t" not in str(e.value) and "s3cr3t" not in repr(e.value)
    assert e.value.__cause__ is None
