from __future__ import annotations

import json
import re

import yaml

from app.contract import iso_utc, token_id
from app.exporter import build_export, to_json, to_yaml
from app.origins import OriginStore

NOW = 1793613600  # 2026-11-02T10:00:00Z
TOKEN_VALUE = "tk_" + "a1b2c3d4e5" * 2 + "f6a7b8c9d"  # 29 chars after the prefix
HASH = "$2a$10$" + "x" * 53


class FakeReader:
    def __init__(self, users=None, acl=None, tokens=None) -> None:
        self._users = users if users is not None else default_users()
        self._acl = acl if acl is not None else default_acl()
        self._tokens = tokens if tokens is not None else default_tokens()

    def list_users(self, include_hash: bool = False):
        rows = []
        for row in self._users:
            row = dict(row)
            if not include_hash:
                row.pop("pass_hash", None)
            rows.append(row)
        return rows

    def list_acl(self):
        return [dict(r) for r in self._acl]

    def list_tokens(self, user=None):
        return [dict(r) for r in self._tokens]


def user(name, role="user", tier=None):
    return {"name": name, "role": role, "tier": tier, "provisioned": False, "pass_hash": HASH}


def default_users():
    return [user("zed"), user("*", "anonymous"), user("admin", "admin"), user("alice", tier="pro")]


def acl(u, topic, perm):
    return {"user": u, "topic": topic, "permission": perm, "read": "r" in perm, "write": "w" in perm,
            "provisioned": False}


def default_acl():
    return [acl("zed", "t2", "ro"), acl("*", "public", "ro"), acl("alice", "t1", "rw"), acl("alice", "a*", "wo")]


def tok(u, label, expires=0, value=TOKEN_VALUE):
    return {"user": u, "token_id": token_id(value), "prefix": value[:7], "label": label, "expires": expires,
            "last_access": 0, "last_origin": "", "provisioned": False, "value": value}


def default_tokens():
    return [tok("alice", "b", NOW + 100, TOKEN_VALUE), tok("alice", "a", 0, "tk_" + "b" * 29)]


def export(tmp_path, reader=None, hashes=False, store=None):
    store = store or OriginStore(tmp_path / "o.json")
    return build_export(reader or FakeReader(), store, include_hashes=hashes, auth_default_access="deny-all", now=NOW)


def test_top_level_keys_and_header(tmp_path):
    doc = export(tmp_path)
    assert list(doc) == ["schema", "generated_at", "source", "server", "users", "acl", "tokens"]
    assert doc["schema"] == 1 and type(doc["schema"]) is int
    assert doc["generated_at"] == iso_utc(NOW)
    assert doc["source"] == {"addon": "ntfy", "auth_schema": 10}
    assert doc["server"] == {"auth_default_access": "deny-all"}


def test_anonymous_only_as_everyone_in_acl(tmp_path):
    doc = export(tmp_path)
    assert [u["name"] for u in doc["users"]] == ["admin", "alice", "zed"]
    assert {"user": "everyone", "topic": "public", "permission": "ro", "origin": "gui"} in doc["acl"]
    assert all(r["user"] != "*" for r in doc["acl"])


def test_hashes_only_on_request(tmp_path):
    plain = export(tmp_path)
    assert all("password_hash" not in u for u in plain["users"])
    assert "$2" not in to_json(plain) and "$2" not in to_yaml(plain)
    full = export(tmp_path, hashes=True)
    assert all(u["password_hash"] == HASH for u in full["users"])


def test_tokens_have_no_values(tmp_path):
    doc = export(tmp_path)
    assert all(set(t) == {"user", "label", "expires", "origin"} for t in doc["tokens"])
    for text in (to_json(doc), to_yaml(doc)):
        assert not re.search(r"tk_[a-z0-9]{29}", text)
    expiring = next(t for t in doc["tokens"] if t["label"] == "b")
    assert expiring["expires"] == iso_utc(NOW + 100)
    assert next(t for t in doc["tokens"] if t["label"] == "a")["expires"] is None


def test_no_secrets_without_hashes_in_any_format(tmp_path):
    doc = export(tmp_path, hashes=False)
    for text in (to_json(doc), to_yaml(doc)):
        assert "$2" not in text and "tk_" not in text


def test_origins_from_store(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_user("alice", "options")
    store.set_acl("alice", "t1", "iac")
    store.set_acl("everyone", "public", "options")
    store.set_token("alice", token_id(TOKEN_VALUE), "iac")
    doc = export(tmp_path, store=store)
    assert next(u for u in doc["users"] if u["name"] == "alice")["origin"] == "options"
    assert next(u for u in doc["users"] if u["name"] == "zed")["origin"] == "gui"
    origins = {(r["user"], r["topic"]): r["origin"] for r in doc["acl"]}
    assert origins[("alice", "t1")] == "iac" and origins[("everyone", "public")] == "options"
    assert origins[("alice", "a*")] == "gui"
    assert next(t for t in doc["tokens"] if t["label"] == "b")["origin"] == "iac"


def test_deterministic_order(tmp_path):
    doc = export(tmp_path)
    assert [(r["user"], r["topic"]) for r in doc["acl"]] == [
        ("alice", "a*"), ("alice", "t1"), ("everyone", "public"), ("zed", "t2")]
    assert [t["label"] for t in doc["tokens"]] == ["a", "b"]
    shuffled = FakeReader(list(reversed(default_users())), list(reversed(default_acl())),
                          list(reversed(default_tokens())))
    other = export(tmp_path, reader=shuffled)
    assert to_json(doc) == to_json(other) and to_yaml(doc) == to_yaml(other)


def test_json_and_yaml_round_trip(tmp_path):
    doc = export(tmp_path, hashes=True)
    assert json.loads(to_json(doc)) == doc
    assert yaml.safe_load(to_yaml(doc)) == doc


def test_yaml_special_strings_survive(tmp_path):
    nasty = ['say "hi"', "a: b", "- dash", "ünï ✓", "#hash", "yes", "null", "123", "", " pad ", "multi\nline", "back\\slash"]
    tokens = [tok("alice", label, 0, "tk_" + f"{i:029d}".replace("0", "c")) for i, label in enumerate(nasty)]
    doc = export(tmp_path, reader=FakeReader(tokens=tokens))
    assert yaml.safe_load(to_yaml(doc)) == doc
    assert json.loads(to_json(doc)) == doc
    assert sorted(t["label"] for t in doc["tokens"]) == sorted(nasty)


def test_empty_collections(tmp_path):
    doc = export(tmp_path, reader=FakeReader(users=[], acl=[], tokens=[]))
    assert doc["users"] == [] and doc["acl"] == [] and doc["tokens"] == []
    assert "users: []" in to_yaml(doc)
    assert yaml.safe_load(to_yaml(doc)) == doc


def test_trailing_newline(tmp_path):
    doc = export(tmp_path)
    assert to_json(doc).endswith("}\n") and to_yaml(doc).endswith("\n")
    assert to_yaml(doc).startswith("schema: 1\n")
