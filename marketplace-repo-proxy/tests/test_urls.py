"""Store URL building and hash masking (app.urls)."""

from __future__ import annotations

from app.access import new_hash
from app.options import Options
from app.urls import internal_base, mask_hash, masked_store_url, store_url, store_urls


def test_store_url_joins_base_without_double_slash():
    h = new_hash()
    assert store_url("http://h:8080/", "o", "r", h) == "http://h:8080/repo/o/r/" + h
    assert store_url("http://h:8080", "o", "r", h) == "http://h:8080/repo/o/r/" + h


def test_mask_hash_keeps_four_chars():
    h = new_hash()
    assert mask_hash(h) == h[:4] + "…"


def test_masked_store_url_never_contains_the_hash():
    h = new_hash()
    url = masked_store_url("http://h:8080", "o", "r", h)
    assert h not in url
    assert url == "http://h:8080/repo/o/r/" + h[:4] + "…"


def test_internal_base_uses_port_8080():
    assert internal_base("h") == "http://h:8080"


def test_store_urls_public_only_when_set():
    h = new_hash()
    internal_only = store_urls(Options(), "proxy-test", "o", "r", h)
    assert internal_only == {"internal": "http://proxy-test:8080/repo/o/r/" + h}
    both = store_urls(Options(public_url="https://addons.example.com"), "proxy-test", "o", "r", h)
    assert both["internal"] == "http://proxy-test:8080/repo/o/r/" + h
    assert both["public"] == "https://addons.example.com/repo/o/r/" + h
