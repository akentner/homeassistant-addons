"""Self-registration (app.registration) and the /data/supervisor.json contract (app.supervisor_state, D-28, D-29).

Registration runs against the in-process fake Supervisor with an injected clone callable (no network); a stub client
is used only where the fake cannot express the case (list order, non-list data, a 409 for an unlisted URL).
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import re
import secrets
import stat
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator

import fake_supervisor
import pytest

from app import supervisor, supervisor_state
from app.access import AccessStore
from app.options import Options, RepoSpec
from app.paths import Paths
from app.registration import LOCAL_USER, Registrar
from app.supervisor import DUPLICATE_ERROR_KEY, CallResult, SupervisorClient, store_slug
from app.supervisor_state import (
    ERROR_CODES,
    MESSAGE_FALLBACK,
    REGISTRATION_STATES,
    SupervisorStateWriter,
    read_supervisor_state,
    registration_message,
    registration_value,
    safe_message,
)
from app.urls import internal_base, store_url

HOST = "addon-host"
SPEC_A = RepoSpec("example-org", "private-addons")
SPEC_B = RepoSpec("example-org", "other")
UNSAFE_RE = re.compile(r"https?://|/repo/|[0-9a-fA-F]{32}|github_pat_|gh[pousr]_")


def _token() -> str:
    # Built at runtime so no token-shaped literal sits in the repository
    return "sentinel" + "-supervisor-" + secrets.token_hex(4)


@pytest.fixture(autouse=True)
def _ticking_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinct timestamps, so `registered_at` moves are observable within one second."""
    counter = itertools.count()
    monkeypatch.setattr(
        supervisor_state, "utc_timestamp", lambda ts=None: f"2026-11-18T12:{next(counter) % 60:02d}:00Z"
    )


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    return p


class Fake:
    """The in-process fake Supervisor plus its base URL; `clone` can be swapped per test."""

    def __init__(self) -> None:
        self.clones: list[str] = []
        self.clone_impl: Callable[[str], str] = lambda url: "Fixture"
        self.state = fake_supervisor.FakeState(_token(), clone=self._clone)
        self.server = fake_supervisor.serve(self.state)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _clone(self, url: str) -> str:
        self.clones.append(url)
        return self.clone_impl(url)

    def client(self, token: str | None = None) -> SupervisorClient:
        return SupervisorClient(self.state.token if token is None else token, base=self.base)

    def calls(self) -> list[str]:
        return [f"{r['method']} {r['path']}" for r in self.state.requests]

    def posts(self) -> int:
        return sum(1 for r in self.state.requests if r["method"] == "POST")


@pytest.fixture
def fake() -> Iterator[Fake]:
    f = Fake()
    try:
        yield f
    finally:
        f.server.shutdown()
        f.server.server_close()


class StubClient:
    """Records calls and answers from preset results (only where the fake cannot express the case)."""

    def __init__(
        self,
        listing: CallResult,
        add: CallResult | None = None,
        reload: CallResult | Exception | None = None,
        remove: CallResult | None = None,
    ) -> None:
        self.listing = listing
        self.add = add or CallResult(True, 200, {})
        self.reload = reload or CallResult(True, 200, {})
        self.remove = remove or CallResult(True, 200, {})
        self.calls: list[str] = []

    def list_repositories(self) -> CallResult:
        self.calls.append("GET")
        return self.listing

    def add_repository(self, url: str) -> CallResult:
        self.calls.append("POST")
        return self.add

    def remove_repository(self, slug: str) -> CallResult:
        self.calls.append(f"DELETE {slug}")
        return self.remove

    def reload_store(self) -> CallResult:
        self.calls.append("RELOAD")
        if isinstance(self.reload, Exception):
            raise self.reload
        return self.reload


def _options(*specs: RepoSpec, register_local: bool = True) -> Options:
    return Options(repositories=specs or (SPEC_A, SPEC_B), register_local=register_local)


def _status(**statuses: str) -> dict:
    """Status doc as status.json holds it; keys `a`/`b` stand for SPEC_A/SPEC_B."""
    names = {"a": SPEC_A.slug, "b": SPEC_B.slug}
    return {"repositories": [{"repository": names[k], "status": v} for k, v in statuses.items()]}


def _registrar(paths: Paths, options: Options, client: Any) -> Registrar:
    return Registrar(paths, options, client, HOST, logging.getLogger("test.store"))


def _url(hash_: str, spec: RepoSpec = SPEC_A) -> str:
    return store_url(internal_base(HOST), spec.owner, spec.name, hash_)


def assert_d29_shape(doc: dict, options: Options) -> None:
    """D-29 interface and D-28 value set; reused by later plans."""
    repos = doc["repositories"]
    assert isinstance(repos, list)
    configured = [spec.slug for spec in options.repositories]
    assert [e["repository"] for e in repos[: len(configured)]] == configured
    for extra in repos[len(configured) :]:
        assert extra["configured"] is False
    for entry in repos:
        assert isinstance(entry["repository"], str)
        assert entry["registration"] in REGISTRATION_STATES
        if "message" in entry:
            message = entry["message"]
            assert isinstance(message, str) and message and len(message) <= 200
            assert not UNSAFE_RE.search(message)


def _doc(paths: Paths, options: Options) -> dict:
    doc = read_supervisor_state(paths)
    assert doc is not None
    assert_d29_shape(doc, options)
    return doc


def _entry(doc: dict, spec: RepoSpec) -> dict:
    return next(e for e in doc["repositories"] if e["repository"] == spec.slug)


def _seed_store(fake: Fake, url: str) -> None:
    """Put a URL into the fake store without an add request."""
    slug = store_slug(url)
    fake.state.repos[slug] = {"slug": slug, "name": "x", "source": url, "url": "", "maintainer": ""}


def _local(paths: Paths, spec: RepoSpec) -> dict | None:
    return AccessStore(paths).get(spec.slug, LOCAL_USER)


# --- registration pass ---------------------------------------------------------------------------------------------


def test_ok_and_missing_is_added_once(paths: Paths, fake: Fake) -> None:
    options = _options()
    registrar = _registrar(paths, options, fake.client())
    registrar.register_pass(_status(a="ok", b="pending"))
    assert fake.calls() == ["GET /store/repositories", "POST /store/repositories"]
    local = _local(paths, SPEC_A)
    assert local is not None and local["source"] == "system"
    assert paths.link_path(SPEC_A.owner, SPEC_A.name, local["hash"]).is_symlink()
    url = _url(local["hash"])
    assert fake.clones == [url]
    entry = _entry(_doc(paths, options), SPEC_A)
    assert entry["registration"] == "registered" and "message" not in entry
    assert entry["in_store"] is True and entry["error"] is None
    assert entry["store_slug"] == store_slug(url)
    assert "…" in entry["masked_url"] and local["hash"] not in entry["masked_url"]
    assert entry["registered_at"] is not None
    assert _local(paths, SPEC_B) is None
    assert _entry(_doc(paths, options), SPEC_B)["registration"] == "missing"


def test_already_present_needs_only_get(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A)
    local = AccessStore(paths).add(SPEC_A.slug, LOCAL_USER, source="system", specs=options.repositories)
    url = _url(local["hash"])
    _seed_store(fake, url)
    _registrar(paths, options, fake.client()).register_pass(_status(a="ok"))
    assert fake.calls() == ["GET /store/repositories"]
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "registered"


def test_presence_does_not_depend_on_list_order(paths: Paths) -> None:
    options = _options()
    store = AccessStore(paths)
    items = []
    for spec in options.repositories:
        local = store.add(spec.slug, LOCAL_USER, source="system", specs=options.repositories)
        items.append({"slug": store_slug(_url(local["hash"], spec)), "url": "from repository.yaml"})
    results = []
    for listing in (items, list(reversed(items))):
        client = StubClient(CallResult(True, 200, listing))
        _registrar(paths, options, client).register_pass(_status(a="ok", b="ok"))
        assert client.calls == ["GET"]
        doc = _doc(paths, options)
        results.append([(e["registration"], e["store_slug"]) for e in doc["repositories"]])
    assert results[0] == results[1]
    assert [r for r, _ in results[0]] == ["registered", "registered"]


def test_url_field_is_never_used_for_presence(paths: Paths) -> None:
    options = _options(SPEC_A)
    local = AccessStore(paths).add(SPEC_A.slug, LOCAL_USER, source="system", specs=options.repositories)
    client = StubClient(CallResult(True, 200, [{"slug": "0000aaaa", "url": _url(local["hash"])}]))
    _registrar(paths, options, client).register_pass(_status(a="ok"))
    assert client.calls == ["GET", "POST"]


@pytest.mark.parametrize("status", ["pending", "no_repository_yaml", "not_found", "auth_failed", "fetch_failed"])
def test_no_registration_without_ok(paths: Paths, fake: Fake, status: str) -> None:
    options = _options(SPEC_A)
    _registrar(paths, options, fake.client()).register_pass(_status(a=status))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert entry["registration"] == "missing" and entry["in_store"] is False
    assert _local(paths, SPEC_A) is None
    assert fake.posts() == 0 and fake.calls() == []


def test_register_local_false_without_entry_makes_no_call(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A, register_local=False)
    _registrar(paths, options, fake.client()).register_pass(_status(a="ok"))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert entry["registration"] == "missing"
    assert entry["message"] == "Registration is turned off (register_local: false)"
    assert fake.calls() == [] and _local(paths, SPEC_A) is None


def test_register_local_false_only_stops_adding(paths: Paths, fake: Fake) -> None:
    options = _options(register_local=False)
    store = AccessStore(paths)
    listed = store.add(SPEC_A.slug, LOCAL_USER, source="system", specs=options.repositories)
    store.add(SPEC_B.slug, LOCAL_USER, source="system", specs=options.repositories)
    url = _url(listed["hash"])
    _seed_store(fake, url)
    _registrar(paths, options, fake.client()).register_pass(_status(a="ok", b="ok"))
    doc = _doc(paths, options)
    assert _entry(doc, SPEC_A)["registration"] == "registered"
    assert _entry(doc, SPEC_B)["registration"] == "missing"
    assert fake.calls() == ["GET /store/repositories"]


def test_duplicate_409_counts_as_registered(paths: Paths) -> None:
    options = _options(SPEC_A)
    client = StubClient(CallResult(True, 200, []), CallResult(False, 409, error_key=DUPLICATE_ERROR_KEY))
    _registrar(paths, options, client).register_pass(_status(a="ok"))
    assert client.calls == ["GET", "POST"]
    entry = _entry(_doc(paths, options), SPEC_A)
    assert entry["registration"] == "registered" and entry["error"] is None


def test_clone_failure_is_an_error_without_supervisor_text(
    paths: Paths, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(url: str) -> str:
        raise ValueError(f"Can't clone {url}: git clone exited with 128")

    fake.clone_impl = failing
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    with caplog.at_level(logging.WARNING, logger="test.store"):
        registrar.register_pass(_status(a="ok"))
        registrar.register_pass(_status(a="ok"))
    assert fake.calls() == ["GET /store/repositories", "POST /store/repositories"] * 2
    entry = _entry(_doc(paths, options), SPEC_A)
    assert entry["registration"] == "error"
    assert (entry["error"], entry["error_status"]) == ("add_rejected", 400)
    assert entry["message"] == "The Supervisor rejected the store URL (HTTP 400)"
    text = paths.supervisor_state_file.read_text()
    local = _local(paths, SPEC_A)
    assert local is not None and local["hash"] not in text
    assert "Can't clone" not in text and "git clone" not in text
    failures = [r.getMessage() for r in caplog.records if "registration of" in r.getMessage()]
    assert len(failures) == 1
    assert local["hash"] not in failures[0] and local["hash"][:4] + "…" in failures[0]


def test_post_timeout_is_an_error_and_the_next_pass_starts_with_get(
    paths: Paths, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()

    def slow(url: str) -> str:
        release.wait(5)  # the Supervisor keeps cloning behind asyncio.shield
        return "Fixture"

    fake.clone_impl = slow
    monkeypatch.setitem(supervisor.TIMEOUTS, ("POST", "/store/repositories"), 0.2)
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    registrar.register_pass(_status(a="ok"))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert (entry["registration"], entry["error"], entry["error_status"]) == ("error", "timeout", None)
    assert entry["message"] == "The Supervisor did not answer in time"
    release.set()
    deadline = time.monotonic() + 5
    while fake.posts() == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    registrar.register_pass(_status(a="ok"))
    assert fake.calls() == ["GET /store/repositories", "POST /store/repositories", "GET /store/repositories"]
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "registered"


def test_store_list_failure_keeps_in_store_and_recovers(paths: Paths, fake: Fake) -> None:
    options = _options()
    registrar = _registrar(paths, options, fake.client())
    registrar.register_pass(_status(a="ok", b="pending"))
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "registered"

    broken = _registrar(paths, options, fake.client(token=_token()))  # 403 from the middleware
    broken.register_pass(_status(a="ok", b="pending"))
    doc = _doc(paths, options)
    entry = _entry(doc, SPEC_A)
    assert (entry["registration"], entry["error"], entry["error_status"]) == ("error", "store_list_unavailable", 403)
    assert entry["in_store"] is True
    assert entry["message"] == "Store list unavailable (HTTP 403)"
    assert _entry(doc, SPEC_B)["registration"] == "missing"
    assert doc["supervisor"]["last_status"] == 403
    assert fake.posts() == 1

    _registrar(paths, options, fake.client()).register_pass(_status(a="ok", b="pending"))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert (entry["registration"], entry["error"], entry["error_status"]) == ("registered", None, None)
    assert fake.posts() == 1


def test_unreachable_supervisor(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A)
    fake.server.shutdown()
    fake.server.server_close()
    _registrar(paths, options, fake.client()).register_pass(_status(a="ok"))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert (entry["registration"], entry["error"], entry["in_store"]) == ("error", "unreachable", False)
    assert entry["message"] == "The Supervisor is unreachable"


def test_non_list_data_is_a_failed_contact(paths: Paths) -> None:
    options = _options(SPEC_A)
    client = StubClient(CallResult(True, 200, {"repositories": []}))
    _registrar(paths, options, client).register_pass(_status(a="ok"))
    assert client.calls == ["GET"]
    entry = _entry(_doc(paths, options), SPEC_A)
    assert (entry["error"], entry["error_status"]) == ("store_list_unavailable", 200)


def test_two_passes_and_a_restart_post_once(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A)
    first = _registrar(paths, options, fake.client())
    first.register_pass(_status(a="ok"))
    first.register_pass(_status(a="ok"))
    hash_before = _local(paths, SPEC_A)["hash"]  # type: ignore[index]
    second = _registrar(paths, options, fake.client())
    second.register_pass(_status(a="ok"))
    assert fake.posts() == 1
    assert _local(paths, SPEC_A)["hash"] == hash_before  # type: ignore[index]
    assert len([e for e in AccessStore(paths).list_entries(SPEC_A.slug) if e["user"] == LOCAL_USER]) == 1


def test_empty_token_records_token_missing(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A)
    _registrar(paths, options, fake.client(token="")).register_pass(_status(a="ok"))
    entry = _entry(_doc(paths, options), SPEC_A)
    assert (entry["registration"], entry["error"]) == ("error", "token_missing")
    assert entry["message"] == "No Supervisor token in the add-on environment"
    assert fake.state.requests == []


def test_exception_in_one_repository_spares_the_next(paths: Paths, fake: Fake, monkeypatch: pytest.MonkeyPatch) -> None:
    options = _options()
    registrar = _registrar(paths, options, fake.client())
    original = registrar.ensure_local

    def broken(spec: RepoSpec) -> dict:
        if spec == SPEC_A:
            raise RuntimeError("boom")
        return original(spec)

    monkeypatch.setattr(registrar, "ensure_local", broken)
    registrar.register_pass(_status(a="ok", b="ok"))
    doc = _doc(paths, options)
    assert (_entry(doc, SPEC_A)["registration"], _entry(doc, SPEC_A)["error"]) == ("error", "internal_error")
    assert _entry(doc, SPEC_B)["registration"] == "registered"


def test_state_file_mode_order_and_secrets(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_B, SPEC_A)
    _registrar(paths, options, fake.client()).register_pass(_status(a="ok", b="ok"))
    path = paths.supervisor_state_file
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    doc = _doc(paths, options)
    assert [e["repository"] for e in doc["repositories"]] == [SPEC_B.slug, SPEC_A.slug]
    text = path.read_text()
    for spec in (SPEC_A, SPEC_B):
        assert _local(paths, spec)["hash"] not in text  # type: ignore[index]
    assert fake.state.token not in text
    assert not re.search(r"/repo/[^ \"]*[0-9a-f]{32}", text)


def test_after_cycle_runs_the_pass(paths: Paths, fake: Fake) -> None:
    options = _options(SPEC_A)
    _registrar(paths, options, fake.client()).after_cycle(_status(a="ok"))
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "registered"


# --- D-28: one registration value from four facts ------------------------------------------------------------------


def _expected(in_store: bool, error: str | None, configured: bool, has_leftover: bool) -> str:
    if error:
        return "error"
    if has_leftover or (not configured and in_store):
        return "leftover"
    return "registered" if in_store else "missing"


@pytest.mark.parametrize(
    ("in_store", "error", "configured", "has_leftover", "value"),
    [
        (False, None, False, False, "missing"),
        (False, None, False, True, "leftover"),
        (False, None, True, False, "missing"),
        (False, None, True, True, "leftover"),
        (False, "timeout", False, False, "error"),
        (False, "timeout", False, True, "error"),
        (False, "timeout", True, False, "error"),
        (False, "timeout", True, True, "error"),
        (True, None, False, False, "leftover"),
        (True, None, False, True, "leftover"),
        (True, None, True, False, "registered"),
        (True, None, True, True, "leftover"),
        (True, "timeout", False, False, "error"),
        (True, "timeout", False, True, "error"),
        (True, "timeout", True, False, "error"),
        (True, "timeout", True, True, "error"),
    ],
)
def test_registration_value_precedence(
    in_store: bool, error: str | None, configured: bool, has_leftover: bool, value: str
) -> None:
    got = registration_value(in_store=in_store, error=error, configured=configured, has_leftover=has_leftover)
    assert got == value == _expected(in_store, error, configured, has_leftover)


def test_registration_states_are_exactly_four() -> None:
    assert REGISTRATION_STATES == ("registered", "missing", "leftover", "error")


def test_seeded_foreign_values_are_recomputed(paths: Paths) -> None:
    options = _options(SPEC_A)
    seeded = {
        "schema": 1,
        "hostname": "old-host",
        "repositories": [
            {
                "repository": SPEC_A.slug,
                "registration": "pending",
                "message": "http://old-host:8080/repo/example-org/private-addons/" + "ab" * 16,
                "in_store": True,
                "store_slug": "0123abcd",
                "error": "not-a-code",
            },
            {"repository": "example-org/gone", "registration": "orphaned", "in_store": True, "store_slug": "4567cdef"},
            {"repository": "example-org/never", "registration": "missing"},
        ],
        "leftovers": "not a list",
    }
    paths.supervisor_state_file.write_text(json.dumps(seeded))
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=options.repositories)
    assert writer.previous_hostname == "old-host"
    doc = _doc(paths, options)
    entry = _entry(doc, SPEC_A)
    assert (entry["registration"], entry["error"], entry["store_slug"]) == ("registered", None, "0123abcd")
    assert "message" not in entry
    gone = doc["repositories"][1]
    assert (gone["repository"], gone["configured"], gone["registration"]) == ("example-org/gone", False, "leftover")
    assert gone["message"] == "No longer configured; its store repository is still listed"
    assert len(doc["repositories"]) == 2
    assert doc["leftovers"] == [] and doc["requests"] == []


def test_new_document_exists_before_any_pass(paths: Paths) -> None:
    options = _options()
    SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=options.repositories)
    doc = _doc(paths, options)
    assert doc["schema"] == 1 and doc["hostname"] == HOST and doc["register_local"] is True
    assert set(doc) >= {"schema", "updated", "register_local", "hostname", "supervisor", "reload", "repositories",
                        "leftovers", "requests"}
    for entry in doc["repositories"]:
        assert entry["registration"] == "missing"
        assert entry["message"] == "Not in the store yet; added after the next successful sync"


def test_registrar_writes_the_document_at_construction(paths: Paths) -> None:
    options = _options()
    _registrar(paths, options, StubClient(CallResult(True, 200, [])))
    assert [e["registration"] for e in _doc(paths, options)["repositories"]] == ["missing", "missing"]


def test_set_repository_rejects_unknown_error_codes(paths: Paths) -> None:
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    with pytest.raises(ValueError):
        writer.set_repository(SPEC_A.slug, in_store=False, error="boom")


# --- D-29: messages from fixed templates only ----------------------------------------------------------------------


def test_safe_message_falls_back_for_unsafe_text() -> None:
    assert safe_message("Can't remove 'http://h:8080/repo/o/r/abcd…'") == MESSAGE_FALLBACK
    assert safe_message("hash " + secrets.token_hex(16)) == MESSAGE_FALLBACK
    assert safe_message("token " + "gh" + "p_" + secrets.token_hex(8)) == MESSAGE_FALLBACK
    assert safe_message(None) is None
    assert safe_message("  \n ") is None
    assert safe_message("two\nlines") == "two lines"
    assert len(safe_message("x" * 500) or "") == 200


def test_registration_message_is_safe_for_every_combination() -> None:
    for value in REGISTRATION_STATES:
        for error in (None, *ERROR_CODES):
            for status in (None, 400, 503):
                for register_local in (True, False):
                    for configured in (True, False):
                        for reasons in ([], ["in_use"], ["in_use", "orphaned"]):
                            message = registration_message(
                                value,
                                error=error,
                                error_status=status,
                                register_local=register_local,
                                configured=configured,
                                leftover_reasons=reasons,
                            )
                            if value == "registered":
                                assert message is None
                                continue
                            assert isinstance(message, str) and message
                            assert safe_message(message) == message


# --- MRP-09: store reload gate (D-08, D-28) ------------------------------------------------------------------------

WALL = 1_800_000_000.0
INTERVAL = 300  # sync_interval 5 minutes


class Clock:
    """Monotonic fake clock for the reload window."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _gated(paths: Paths, options: Options, client: Any, clock: Clock) -> Registrar:
    return Registrar(paths, options, client, HOST, logging.getLogger("test.store"), clock=clock, wall=lambda: WALL)


def _gate_options(*specs: RepoSpec, register_local: bool = True) -> Options:
    return Options(repositories=specs or (SPEC_A, SPEC_B), register_local=register_local, sync_interval=5)


@pytest.fixture
def quiet_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake's reload runs `git ls-remote` per store URL; the internal host does not exist here."""
    monkeypatch.setattr(fake_supervisor, "_ls_remote_head", lambda source: None)


def _registered_stub(paths: Paths, options: Options, reload: CallResult | Exception | None = None) -> StubClient:
    """A stub whose store lists the `local` URL of every configured repository."""
    store = AccessStore(paths)
    items = []
    for spec in options.repositories:
        local = store.add(spec.slug, LOCAL_USER, source="system", specs=options.repositories)
        items.append({"slug": store_slug(_url(local["hash"], spec))})
    return StubClient(CallResult(True, 200, items), reload=reload)


def _reload_doc(paths: Paths) -> dict:
    doc = read_supervisor_state(paths)
    assert doc is not None
    return doc["reload"]


def _store_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("store reload: ")]


@pytest.mark.usefixtures("quiet_reload")
def test_reload_after_a_head_change_of_a_registered_repository(
    paths: Paths, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    options = _gate_options(SPEC_A)
    registrar = _gated(paths, options, fake.client(), Clock())
    registrar.after_cycle(_status(a="ok"))
    assert fake.calls() == ["GET /store/repositories", "POST /store/repositories"]
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert fake.calls()[2:] == ["GET /store/repositories", "POST /store/reload"]
    assert fake.state.reloads == 1
    state = _reload_doc(paths)
    assert (state["last_result"], state["pending"], state["message"]) == ("ok", False, "")
    assert state["last_requested"] == "2027-01-15T08:00:00Z"
    assert registrar.reload_pending is False
    assert _store_lines(caplog) == ["store reload: ok"]


@pytest.mark.usefixtures("quiet_reload")
def test_no_reload_for_repositories_outside_the_store_before_the_pass(paths: Paths, fake: Fake) -> None:
    # Added in this very pass: the add already cloned the current head
    options = _gate_options(SPEC_A)
    registrar = _gated(paths, options, fake.client(), Clock())
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert fake.calls() == ["GET /store/repositories", "POST /store/repositories"]
    # Registration off and nothing listed: missing
    other = Paths.under(paths.data_dir.parent / "other")
    other.data_dir.mkdir(parents=True)
    off = _gate_options(SPEC_B, register_local=False)
    client = StubClient(CallResult(True, 200, []))
    _gated(other, off, client, Clock()).after_cycle(_status(b="ok"), frozenset({SPEC_B.key}))
    assert "RELOAD" not in client.calls
    assert _entry(_doc(other, off), SPEC_B)["registration"] == "missing"
    assert fake.state.reloads == 0


def test_no_reload_for_an_error_without_a_listed_url(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    failing = StubClient(CallResult(False, 503))
    registrar = _gated(paths, options, failing, Clock())
    registrar.after_cycle(_status(a="ok"))
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "error"
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert "RELOAD" not in failing.calls


def test_reload_for_a_leftover_repository_whose_url_is_in_the_store(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options)
    current = client.listing.data[0]["slug"]
    seeded = {
        "schema": 1,
        "repositories": [{"repository": SPEC_A.slug, "in_store": True, "store_slug": current}],
        "leftovers": [{"repository": SPEC_A.slug, "store_slug": "89abcdef", "user": "local.89abcdef",
                       "reason": "in_use"}],
    }
    paths.supervisor_state_file.write_text(json.dumps(seeded))
    registrar = _gated(paths, options, client, Clock())
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "leftover"
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert client.calls == ["GET", "RELOAD"]


def test_two_changed_repositories_give_one_reload(paths: Paths) -> None:
    options = _gate_options()
    client = _registered_stub(paths, options)
    registrar = _gated(paths, options, client, Clock())
    registrar.after_cycle(_status(a="ok", b="ok"))
    assert client.calls == ["GET"]
    registrar.after_cycle(_status(a="ok", b="ok"), frozenset({SPEC_A.key, SPEC_B.key}))
    assert client.calls == ["GET", "GET", "RELOAD"]


def test_no_reload_without_change_and_no_calls_without_repositories(paths: Paths) -> None:
    options = _gate_options()
    client = _registered_stub(paths, options)
    registrar = _gated(paths, options, client, Clock())
    registrar.after_cycle(_status(a="ok", b="ok"))
    registrar.after_cycle(_status(a="ok", b="ok"), frozenset())
    assert client.calls == ["GET", "GET"]
    empty = Paths.under(paths.data_dir.parent / "empty")
    empty.data_dir.mkdir(parents=True)
    nothing = StubClient(CallResult(True, 200, []))
    _gated(empty, Options(sync_interval=5), nothing, Clock()).after_cycle({"repositories": []}, frozenset())
    assert nothing.calls == []


def test_reload_inside_the_window_is_deferred_and_the_boundary_opens_it(
    paths: Paths, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options)
    clock = Clock()
    registrar = _gated(paths, options, client, clock)
    registrar.after_cycle(_status(a="ok"))
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert client.calls.count("RELOAD") == 1
    assert registrar.interval_seconds == INTERVAL
    clock.now += INTERVAL - 1
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert client.calls.count("RELOAD") == 1
    assert registrar.reload_pending is True
    assert _reload_doc(paths)["pending"] is True
    assert registrar.window_open() is False
    lines = _store_lines(caplog)
    assert lines[0] == "store reload: ok"
    assert lines[1] == "store reload: deferred until 2027-01-15T08:00:01Z"
    clock.now += 1
    assert registrar.window_open() is True


def test_failed_reload_keeps_pending_and_closes_the_window(paths: Paths, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    options = _gate_options(SPEC_A)
    hash_ = secrets.token_hex(16)
    text = f"Can't pull {_url(hash_)}"
    client = _registered_stub(paths, options, reload=CallResult(False, 400, message=text))
    clock = Clock()
    registrar = _gated(paths, options, client, clock)
    registrar.after_cycle(_status(a="ok"))
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert client.calls.count("RELOAD") == 1
    state = _reload_doc(paths)
    assert (state["last_result"], state["pending"]) == ("failed", True)
    assert hash_ not in state["message"] and state["message"].startswith("Can't pull ")
    assert hash_ not in paths.supervisor_state_file.read_text()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "store reload" in r.getMessage()]
    assert len(warnings) == 1 and warnings[0].getMessage().startswith("store reload: failed: Can't pull ")
    assert hash_ not in warnings[0].getMessage()
    clock.now += INTERVAL - 1
    assert registrar.window_open() is False
    clock.now += 1
    assert registrar.window_open() is True


def test_reload_window_closes_before_the_call(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options, reload=RuntimeError("boom"))
    registrar = _gated(paths, options, client, Clock())
    registrar.after_cycle(_status(a="ok"))
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert client.calls.count("RELOAD") == 1
    assert registrar.last_reload_at is not None
    assert registrar.window_open() is False
    assert registrar.reload_pending is True
    assert _reload_doc(paths)["pending"] is True


def test_set_reload_validates_and_masks(paths: Paths) -> None:
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    assert writer.reload_state() == {"last_requested": None, "last_result": None, "pending": False, "message": ""}
    with pytest.raises(ValueError):
        writer.set_reload(last_result="maybe")
    hash_ = secrets.token_hex(16)
    writer.set_reload(last_result="failed", pending=True, message=f"x {_url(hash_)}")
    state = writer.reload_state()
    assert state["pending"] is True and state["last_result"] == "failed"
    assert hash_ not in state["message"]
    state["pending"] = False
    assert writer.reload_state()["pending"] is True  # a copy


def test_work_due_follows_pending_and_the_window(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options)
    clock = Clock()
    registrar = _gated(paths, options, client, clock)
    assert registrar.work_due() is False  # nothing owed
    registrar.after_cycle(_status(a="ok"))
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    clock.now += 10
    registrar.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert registrar.reload_pending is True
    assert registrar.work_due() is False  # owed, window closed
    registrar.run_due()
    assert client.calls.count("RELOAD") == 1
    clock.now += INTERVAL - 10
    assert registrar.work_due() is True  # boundary
    registrar.run_due()
    assert client.calls.count("RELOAD") == 2
    assert registrar.reload_pending is False and _reload_doc(paths)["pending"] is False
    assert registrar.work_due() is False
    registrar.run_due()
    assert client.calls.count("RELOAD") == 2


def test_restart_sends_a_persisted_pending_reload_after_the_first_cycle(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options)
    clock = Clock()
    first = _gated(paths, options, client, clock)
    first.after_cycle(_status(a="ok"))
    first.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    clock.now += 1
    first.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert _reload_doc(paths)["pending"] is True
    restarted_client = StubClient(client.listing)
    restarted = _gated(paths, options, restarted_client, Clock())
    assert restarted.reload_pending is True and restarted.work_due() is True
    restarted.after_cycle(_status(a="ok"), frozenset())
    assert restarted_client.calls == ["GET", "RELOAD"]
    assert _reload_doc(paths)["pending"] is False
    restarted.after_cycle(_status(a="ok"), frozenset())
    assert restarted_client.calls == ["GET", "RELOAD", "GET"]


def test_restart_without_pending_and_unchanged_heads_sends_no_reload(paths: Paths) -> None:
    options = _gate_options(SPEC_A)
    client = _registered_stub(paths, options)
    first = _gated(paths, options, client, Clock())
    first.after_cycle(_status(a="ok"))
    first.after_cycle(_status(a="ok"), frozenset({SPEC_A.key}))
    assert _reload_doc(paths)["pending"] is False
    restarted_client = StubClient(client.listing)
    restarted = _gated(paths, options, restarted_client, Clock())
    assert restarted.work_due() is False
    restarted.after_cycle(_status(a="ok"), frozenset())
    assert restarted_client.calls == ["GET"]


# --- MRP-10: removal through the request queue (D-02, D-09, D-10, D-11, D-27, D-28, D-29) --------------------------

HEX32_RE = re.compile(r"[0-9a-fA-F]{32}")
INVALID_REQUEST_LINE = "ignored an invalid supervisor request file"


def _ok_status(*specs: RepoSpec) -> dict:
    return {"repositories": [{"repository": spec.slug, "status": "ok"} for spec in specs]}


def _register(paths: Paths, fake: Fake, *specs: RepoSpec) -> dict[str, dict]:
    """Register `specs` through the fake with register_local true; returns their `local` entries by key."""
    _registrar(paths, _options(*specs), fake.client()).register_pass(_ok_status(*specs))
    entries = {spec.key: _local(paths, spec) for spec in specs}
    assert all(entries.values())
    return entries  # type: ignore[return-value]


def _slug_of(entry: dict, spec: RepoSpec = SPEC_A) -> str:
    return store_slug(_url(entry["hash"], spec))


def _request(paths: Paths, repository: str = SPEC_A.slug, action: str = "remove", **extra: Any) -> str:
    """Write a request file like `mrp local remove` does; returns its id."""
    id_ = secrets.token_hex(8)
    directory = paths.supervisor_requests_dir
    directory.mkdir(parents=True, exist_ok=True)
    doc = {"id": id_, "action": action, "repository": repository, "created": "2026-11-18T12:00:00Z", **extra}
    (directory / f"{id_}.json").write_text(json.dumps(doc))
    return id_


def _deletes(fake: Fake) -> list[str]:
    return [r["slug"] for r in fake.state.requests if r["method"] == "DELETE"]


def _requests(paths: Paths) -> list[dict]:
    doc = read_supervisor_state(paths)
    assert doc is not None
    return doc["requests"]


def _outcome(paths: Paths) -> tuple[str, str]:
    last = _requests(paths)[-1]
    return last["result"], last["code"]


def _messages(caplog: pytest.LogCaptureFixture, level: int = logging.DEBUG) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= level]


def _link(paths: Paths, entry: dict, spec: RepoSpec = SPEC_A) -> Path:
    return paths.link_path(spec.owner, spec.name, entry["hash"])


def test_remove_request_deletes_the_recorded_slug_and_revokes_local(paths: Paths, fake: Fake) -> None:
    old = _register(paths, fake, SPEC_A)[SPEC_A.key]
    slug = _slug_of(old)
    options = _options(SPEC_A, register_local=False)
    registrar = _registrar(paths, options, fake.client())
    id_ = _request(paths)
    assert registrar.work_due() is True
    registrar.run_due()
    assert _deletes(fake) == [slug] and slug not in fake.state.repos
    assert _local(paths, SPEC_A) is None and not os.path.lexists(_link(paths, old))
    doc = _doc(paths, options)
    entry = _entry(doc, SPEC_A)
    assert (entry["registration"], entry["in_store"]) == ("missing", False)
    last = doc["requests"][-1]
    assert set(last) == {"id", "action", "repository", "result", "code", "finished"}
    assert (last["id"], last["action"], last["repository"], last["result"], last["code"]) == (
        id_, "remove", SPEC_A.slug, "done", "")
    assert list(paths.supervisor_requests_dir.iterdir()) == []
    assert registrar.work_due() is False


def test_remove_request_with_register_local_enabled_is_rejected(paths: Paths, fake: Fake) -> None:
    old = _register(paths, fake, SPEC_A)[SPEC_A.key]
    sent = len(fake.state.requests)
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    _request(paths)
    registrar.run_due()
    assert fake.state.requests[sent:] == []
    assert _outcome(paths) == ("rejected", "register_local_enabled")
    assert _local(paths, SPEC_A) == old
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "registered"


def test_unconfigured_repository_is_never_removed_by_a_pass_and_shows_leftover(paths: Paths, fake: Fake) -> None:
    _register(paths, fake, SPEC_A, SPEC_B)
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    for _ in range(3):
        registrar.after_cycle(_ok_status(SPEC_A))
    assert _deletes(fake) == []
    doc = _doc(paths, options)
    other = doc["repositories"][1]
    assert (other["repository"], other["configured"], other["registration"]) == (SPEC_B.slug, False, "leftover")
    assert _local(paths, SPEC_B) is not None


def test_remove_request_for_an_unconfigured_repository_drops_it(paths: Paths, fake: Fake) -> None:
    entries = _register(paths, fake, SPEC_A, SPEC_B)
    slug_b = _slug_of(entries[SPEC_B.key], SPEC_B)
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    _request(paths, SPEC_B.slug)
    registrar.run_due()
    assert _deletes(fake) == [slug_b]
    assert _outcome(paths) == ("done", "")
    doc = _doc(paths, options)
    assert [e["repository"] for e in doc["repositories"]] == [SPEC_A.slug]
    assert _local(paths, SPEC_B) is None
    assert _local(paths, SPEC_A) == entries[SPEC_A.key]


@pytest.mark.parametrize("repository", ["example-org/unknown", "not a repository", "../escape"])
def test_remove_request_for_an_unknown_repository_is_rejected(paths: Paths, repository: str) -> None:
    client = StubClient(CallResult(True, 200, []))
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), client)
    _request(paths, repository)
    registrar.run_due()
    assert client.calls == []
    assert _outcome(paths) == ("rejected", "repository_unknown")


def test_remove_request_with_a_failed_store_list_changes_nothing(paths: Paths, fake: Fake) -> None:
    old = _register(paths, fake, SPEC_A)[SPEC_A.key]
    options = _options(SPEC_A, register_local=False)
    before = read_supervisor_state(paths)
    client = StubClient(CallResult(False, 503))
    registrar = _registrar(paths, options, client)
    _request(paths)
    registrar.run_due()
    assert client.calls == ["GET"]
    assert _outcome(paths) == ("failed", "store_list_unavailable")
    assert _local(paths, SPEC_A) == old
    doc = _doc(paths, options)
    assert doc["leftovers"] == [] and doc["repositories"] == before["repositories"]


def _refused(paths: Paths, fake: Fake) -> tuple[Registrar, Options, dict, str]:
    """A registered repository whose removal the fake refuses (in use); register_local is false."""
    old = _register(paths, fake, SPEC_A)[SPEC_A.key]
    slug = _slug_of(old)
    fake.state.in_use.add(slug)
    options = _options(SPEC_A, register_local=False)
    registrar = _registrar(paths, options, fake.client())
    _request(paths)
    registrar.run_due()
    return registrar, options, old, slug


def test_refused_remove_records_a_leftover_and_is_never_retried(
    paths: Paths, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    registrar, options, old, slug = _refused(paths, fake)
    assert _deletes(fake) == [slug]
    assert _outcome(paths) == ("refused", "in_use")
    doc = _doc(paths, options)
    (leftover,) = doc["leftovers"]
    assert (leftover["repository"], leftover["store_slug"], leftover["user"]) == (SPEC_A.slug, slug, LOCAL_USER)
    assert (leftover["reason"], leftover["revoked"]) == ("in_use", False)
    assert "…" in leftover["masked_url"] and old["hash"] not in leftover["masked_url"]
    assert isinstance(leftover["since"], str) and leftover["since"].endswith("Z")
    assert "used by installed apps" in leftover["message"] and old["hash"] not in leftover["message"]
    entry = _entry(doc, SPEC_A)
    assert (entry["registration"], entry["in_store"]) == ("leftover", True)
    assert entry["message"] == "1 old store repository left (in_use); see mrp local status"
    assert _local(paths, SPEC_A) == old and _link(paths, old).is_symlink()
    store_warnings = [m for m in _messages(caplog, logging.WARNING) if m.startswith("store: ")]
    assert store_warnings == [f"store: {SPEC_A.slug} leftover {slug} (in_use)"]
    for _ in range(3):
        registrar.after_cycle(_ok_status(SPEC_A))
    assert _deletes(fake) == [slug]
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "leftover"
    assert not HEX32_RE.search(paths.supervisor_state_file.read_text())
    assert not HEX32_RE.search(caplog.text)


def test_dropping_a_leftover_while_listed_returns_to_registered(paths: Paths) -> None:
    options = _options(SPEC_A)
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=options.repositories)
    writer.set_repository(SPEC_A.slug, in_store=True, store_slug="0a1b2c3d", masked_url="masked")
    writer.add_leftover(
        repository=SPEC_A.slug, store_slug="11223344", user="local.11223344", masked_url="", reason="in_use"
    )
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "leftover"
    assert writer.drop_leftover("11223344") is True
    doc = _doc(paths, options)
    assert doc["leftovers"] == [] and _entry(doc, SPEC_A)["registration"] == "registered"
    assert writer.drop_leftover("11223344") is False


def test_leftover_gone_from_the_store_is_dropped_by_the_pass_without_delete(
    paths: Paths, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    registrar, options, old, slug = _refused(paths, fake)
    # The operator uninstalled the add-ons and removed the store repository in the Supervisor UI
    fake.state.in_use.discard(slug)
    fake.state.repos.pop(slug)
    caplog.set_level(logging.INFO)
    registrar.register_pass(_ok_status(SPEC_A))
    assert _deletes(fake) == [slug]
    doc = _doc(paths, options)
    assert doc["leftovers"] == []
    entry = _entry(doc, SPEC_A)
    assert (entry["registration"], entry["in_store"]) == ("missing", False)
    assert _local(paths, SPEC_A) is None and not os.path.lexists(_link(paths, old))
    assert f"store: leftover {slug} of {SPEC_A.slug} is gone; dropped" in _messages(caplog, logging.INFO)


def test_unconfigured_repository_gone_from_the_store_is_dropped_without_delete_or_request(
    paths: Paths, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    entry_b = _register(paths, fake, SPEC_B)[SPEC_B.key]
    fake.state.repos.pop(_slug_of(entry_b, SPEC_B))
    options = _options(SPEC_A, register_local=False)  # no `local` entry wanted or present for SPEC_A
    registrar = _registrar(paths, options, fake.client())
    assert len(_doc(paths, options)["repositories"]) == 2
    caplog.set_level(logging.INFO)
    sent = len(fake.state.requests)
    registrar.register_pass(_ok_status(SPEC_A))
    assert fake.calls()[sent:] == ["GET /store/repositories"]
    assert _deletes(fake) == []
    assert [e["repository"] for e in _doc(paths, options)["repositories"]] == [SPEC_A.slug]
    assert _local(paths, SPEC_B) is None
    line = f"store: {SPEC_B.slug} is no longer configured and its store repository is gone; local entry revoked"
    assert line in _messages(caplog, logging.INFO)


def test_repeated_remove_request_after_success_is_done_without_delete(paths: Paths, fake: Fake) -> None:
    old = _register(paths, fake, SPEC_A)[SPEC_A.key]
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), fake.client())
    _request(paths)
    registrar.run_due()
    _request(paths)
    registrar.run_due()
    assert _deletes(fake) == [_slug_of(old)]
    assert [r["result"] for r in _requests(paths)] == ["done", "done"]


def test_remove_request_with_register_local_enabled_retries_only_leftovers(paths: Paths, fake: Fake) -> None:
    current = _register(paths, fake, SPEC_A)[SPEC_A.key]
    old_url = _url(secrets.token_hex(16))
    _seed_store(fake, old_url)
    old_slug = store_slug(old_url)
    options = _options(SPEC_A)
    registrar = _registrar(paths, options, fake.client())
    registrar.state.add_leftover(
        repository=SPEC_A.slug, store_slug=old_slug, user="local." + old_slug, masked_url="", reason="in_use",
        revoked=True,
    )
    assert _entry(_doc(paths, options), SPEC_A)["registration"] == "leftover"
    _request(paths)
    registrar.run_due()
    assert _deletes(fake) == [old_slug]
    assert _outcome(paths) == ("done", "")
    doc = _doc(paths, options)
    assert doc["leftovers"] == [] and _entry(doc, SPEC_A)["registration"] == "registered"
    assert _local(paths, SPEC_A) == current and _slug_of(current) in fake.state.repos


def _write_raw(paths: Paths, name: str, content: str) -> Path:
    paths.supervisor_requests_dir.mkdir(parents=True, exist_ok=True)
    path = paths.supervisor_requests_dir / name
    path.write_text(content)
    return path


def _valid(id_: str, **changes: Any) -> str:
    doc = {"id": id_, "action": "remove", "repository": SPEC_A.slug, "created": "2026-11-18T12:00:00Z"}
    doc.update(changes)
    return json.dumps({k: v for k, v in doc.items() if v is not None})


@pytest.mark.parametrize(
    "kind", ["bad_name", "not_json", "missing_key", "revoke_old_key", "id_mismatch", "repository_type", "array"]
)
def test_invalid_request_file_is_deleted_without_supervisor_calls(
    paths: Paths, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    id_ = secrets.token_hex(8)
    name, content = f"{id_}.json", _valid(id_)
    if kind == "bad_name":
        name = "remove-me.json"
    elif kind == "not_json":
        content = "{not json"
    elif kind == "missing_key":
        content = _valid(id_, created=None)
    elif kind == "revoke_old_key":
        content = json.dumps({**json.loads(_valid(id_)), "revoke_old": True})
    elif kind == "id_mismatch":
        content = _valid(secrets.token_hex(8))
    elif kind == "repository_type":
        content = json.dumps({**json.loads(_valid(id_)), "repository": 123})
    else:
        content = "[]"
    path = _write_raw(paths, name, content)
    client = StubClient(CallResult(True, 200, []))
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), client)
    caplog.set_level(logging.INFO)
    assert registrar.work_due() is True
    registrar.run_due()
    assert not path.exists()
    assert client.calls == []
    assert _requests(paths) == []
    assert INVALID_REQUEST_LINE in _messages(caplog, logging.WARNING)
    assert registrar.work_due() is False


def test_symlinked_request_file_is_deleted_and_its_target_kept(paths: Paths, tmp_path: Path) -> None:
    id_ = secrets.token_hex(8)
    target = tmp_path / "target.json"
    target.write_text(_valid(id_))
    paths.supervisor_requests_dir.mkdir(parents=True)
    link = paths.supervisor_requests_dir / f"{id_}.json"
    link.symlink_to(target)
    client = StubClient(CallResult(True, 200, []))
    _registrar(paths, _options(SPEC_A, register_local=False), client).run_due()
    assert not os.path.lexists(link) and target.exists()
    assert client.calls == [] and _requests(paths) == []


def test_request_with_an_unknown_action_is_rejected_as_invalid_request(paths: Paths) -> None:
    client = StubClient(CallResult(True, 200, []))
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), client)
    id_ = _request(paths, action="purge")
    registrar.run_due()
    assert client.calls == []
    last = _requests(paths)[-1]
    assert (last["id"], last["result"], last["code"]) == (id_, "rejected", "invalid_request")


def _stub_registered(paths: Paths, options: Options) -> StubClient:
    """`local` entries listed by a stub store, with the slugs recorded by one pass."""
    client = _registered_stub(paths, options)
    _registrar(paths, options, client).register_pass(_ok_status(*options.repositories))
    client.calls.clear()
    return client


def test_request_file_is_unlinked_before_execution(paths: Paths) -> None:
    options = _options(SPEC_A, register_local=False)
    client = _stub_registered(paths, options)
    id_ = _request(paths)
    path = paths.supervisor_requests_dir / f"{id_}.json"
    seen: list[bool] = []
    listing = client.list_repositories

    def checking() -> CallResult:
        seen.append(path.exists())
        return listing()

    client.list_repositories = checking  # type: ignore[method-assign]
    _registrar(paths, options, client).run_due()
    assert seen == [False]
    assert _outcome(paths) == ("done", "")


def test_request_created_during_run_due_is_handled_in_the_next_run(paths: Paths) -> None:
    options = _options(SPEC_A, register_local=False)
    client = _stub_registered(paths, options)
    listing = client.list_repositories
    created: list[str] = []

    def adding() -> CallResult:
        if not created:
            created.append(_request(paths))
        return listing()

    client.list_repositories = adding  # type: ignore[method-assign]
    registrar = _registrar(paths, options, client)
    first = _request(paths)
    registrar.run_due()
    assert [r["id"] for r in _requests(paths)] == [first]
    assert registrar.work_due() is True
    registrar.run_due()
    assert [r["id"] for r in _requests(paths)] == [first, created[0]]
    assert registrar.work_due() is False


def test_work_due_follows_request_files_and_ignores_temporary_files(paths: Paths) -> None:
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), StubClient(CallResult(True, 200, [])))
    assert registrar.work_due() is False
    temporary = _write_raw(paths, ".0123456789abcdef.json.x1y2.tmp", "{}")
    (paths.supervisor_requests_dir / "subdir").mkdir()
    assert registrar.work_due() is False
    assert registrar.pending_requests() == []
    _request(paths)
    assert registrar.work_due() is True
    assert len(registrar.pending_requests()) == 1
    registrar.run_due()
    assert registrar.work_due() is False and temporary.exists()


def test_pending_requests_are_sorted_by_mtime_then_name(paths: Paths) -> None:
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), StubClient(CallResult(True, 200, [])))
    ids = [_request(paths) for _ in range(3)]
    for offset, id_ in enumerate(ids):
        stamp = 1_800_000_000 - offset
        os.utime(paths.supervisor_requests_dir / f"{id_}.json", (stamp, stamp))
    assert [p.stem for p in registrar.pending_requests()] == list(reversed(ids))


def test_record_request_keeps_the_last_twenty_and_validates(paths: Paths) -> None:
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    for index in range(supervisor_state.MAX_REQUESTS + 5):
        writer.record_request(id=f"{index:016x}", action="remove", repository=SPEC_A.slug, result="done")
    requests = _requests(paths)
    assert len(requests) == 20 and requests[0]["id"] == f"{5:016x}" and requests[-1]["id"] == f"{24:016x}"
    assert requests[-1]["code"] == "" and requests[-1]["finished"].endswith("Z")
    with pytest.raises(ValueError):
        writer.record_request(id="0" * 16, action="remove", repository=SPEC_A.slug, result="maybe")
    assert supervisor_state.REQUEST_RESULTS == ("done", "refused", "failed", "rejected")


def test_add_leftover_keeps_since_validates_reason_and_masks(paths: Paths) -> None:
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    secret = secrets.token_hex(16)
    writer.add_leftover(
        repository=SPEC_A.slug, store_slug="11223344", user=LOCAL_USER, masked_url="masked", reason="in_use",
        message=f"Can't remove 'http://{HOST}:8080/repo/example-org/private-addons/{secret}'",
    )
    (first,) = writer.leftovers(SPEC_A.slug.upper())
    writer.add_leftover(
        repository=SPEC_A.slug, store_slug="11223344", user=LOCAL_USER, masked_url="masked", reason="error"
    )
    (second,) = writer.leftovers()
    assert second["since"] == first["since"] and second["reason"] == "error"
    assert secret not in paths.supervisor_state_file.read_text()
    assert writer.leftovers("example-org/other") == []
    with pytest.raises(ValueError):
        writer.add_leftover(repository=SPEC_A.slug, store_slug="11223344", user=None, masked_url="", reason="gone")
    assert supervisor_state.LEFTOVER_REASONS == ("in_use", "error", "interrupted", "orphaned")


def test_drop_repository_removes_only_an_unconfigured_leftover_entry(paths: Paths) -> None:
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    writer.set_repository(SPEC_B.slug, in_store=True, store_slug="0a1b2c3d", configured=False)
    assert writer.unconfigured_repositories() == [SPEC_B.slug]
    assert writer.drop_repository(SPEC_A.slug) is False
    assert writer.drop_repository(SPEC_B.slug.upper()) is True
    assert [e["repository"] for e in _doc(paths, _options(SPEC_A))["repositories"]] == [SPEC_A.slug]
    assert writer.unconfigured_repositories() == []


def test_carried_leftovers_and_requests_are_type_checked(paths: Paths) -> None:
    secret = secrets.token_hex(16)
    seeded = {
        "schema": 1,
        "repositories": [{"repository": SPEC_A.slug, "in_store": True, "store_slug": "0a1b2c3d"}],
        "leftovers": [
            {"repository": SPEC_A.slug, "store_slug": "11223344", "user": "local", "reason": "in_use",
             "masked_url": f"http://x/{secret}", "message": secret, "revoked": "yes"},
            {"repository": SPEC_A.slug, "store_slug": "not-a-slug", "reason": "in_use"},
            {"repository": 7, "store_slug": "55667788", "reason": "in_use"},
        ],
        "requests": [{"id": f"{i:016x}", "result": "done"} for i in range(30)],
    }
    paths.supervisor_state_file.write_text(json.dumps(seeded))
    writer = SupervisorStateWriter(paths, hostname=HOST, register_local=True, specs=(SPEC_A,))
    (leftover,) = writer.leftovers()
    assert leftover["store_slug"] == "11223344" and leftover["revoked"] is False
    assert leftover["masked_url"] == "" and secret not in json.dumps(leftover)
    assert len(_requests(paths)) == 20


def test_remove_request_with_another_delete_error_fails_and_changes_nothing(paths: Paths) -> None:
    options = _options(SPEC_A, register_local=False)
    client = _stub_registered(paths, options)
    client.remove = CallResult(False, 500, message="boom")
    before = read_supervisor_state(paths)
    local = _local(paths, SPEC_A)
    _request(paths)
    _registrar(paths, options, client).run_due()
    assert client.calls == ["GET", f"DELETE {before['repositories'][0]['store_slug']}"]
    assert _outcome(paths) == ("failed", "remove_failed")
    doc = _doc(paths, options)
    assert doc["leftovers"] == [] and doc["repositories"] == before["repositories"]
    assert _local(paths, SPEC_A) == local


def test_remove_request_without_a_recorded_registration_is_not_registered(paths: Paths) -> None:
    client = StubClient(CallResult(True, 200, []))
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), client)
    _request(paths)
    registrar.run_due()
    assert client.calls == []
    assert _outcome(paths) == ("rejected", "not_registered")


def test_request_file_that_cannot_be_unlinked_never_runs_or_keeps_the_loop_busy(
    paths: Paths, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = StubClient(CallResult(True, 200, []))
    registrar = _registrar(paths, _options(SPEC_A, register_local=False), client)
    id_ = _request(paths)
    real_unlink = Path.unlink

    def refusing(self: Path, missing_ok: bool = False) -> None:
        if self.name == f"{id_}.json":
            raise PermissionError("read-only")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refusing)
    caplog.set_level(logging.INFO)
    registrar.run_due()
    assert client.calls == [] and _requests(paths) == []
    assert INVALID_REQUEST_LINE in _messages(caplog, logging.WARNING)
    assert registrar.work_due() is False
