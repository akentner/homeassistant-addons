"""Sync supervisor: runs provider cycles, writes results, keeps state.json fresh (implements Controller)."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.engine import config as config_mod
from app.engine import usage as usage_mod
from app.engine.config import Config, ProviderLoadError
from app.engine.guard import check_shrink
from app.engine.merge import Merged, MergeError, merge
from app.engine.redact import Redactor
from app.engine.state import StateStore, iso
from app.engine.writer import WriteError, read_secrets, write_files, write_secrets
from app.providers.base import Problem, Provider, ProviderError, Snapshot

log = logging.getLogger("secrets_sync")

TOOLS = {"bitwarden": "bw", "sops": "sops"}
HEARTBEAT = 30  # seconds between state refreshes while idle (keeps age_seconds honest)
MANUAL_MIN_GAP = 10  # a manual sync is allowed when the last attempt is older than this
BACKOFF_START = 30
USAGE_MIN_GAP = 60  # seconds between usage scans (error backoff cycles run more often)
PREVIEW_WAIT = 90


class SyntheticFailure(Exception):
    def __init__(self, code: str, message: str, name: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.name = name


@dataclass
class _Fetch:
    name: str
    snapshot: Snapshot | None
    code: str | None = None
    message: str = ""
    problems: list[Problem] | None = None
    collision: bool = False


class Supervisor:
    def __init__(self, config: Config, providers: Mapping[str, Provider] | None = None,
                 clock: Callable[[], float] = time.time, redactor: Redactor | None = None,
                 probe_versions: bool = True) -> None:
        self.cfg = config
        self._clock = clock
        self.redactor = redactor or Redactor()
        self._providers: dict[str, Provider] = dict(providers or {})
        self._cycle_lock = threading.RLock()
        self._ctl = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._running = False
        self._pending = False
        self._force = False
        self._last_attempt = 0.0
        self._fails = 0
        self._next_at = 0.0
        self._last_good: dict[str, Snapshot] = {}
        self._pinfo: dict[str, dict[str, Any]] = {}
        self._last_written: dict[str, str] | None = None
        self._active: set[str] = set()
        self._usage_at: float | None = None
        self._tokens: dict[str, str] = {}  # check_token seen at the last successful fetch per provider
        self._next_probe: float | None = None
        self._check_errors: dict[str, str] = {}  # provider -> error code currently announced
        self._announced: dict[str, str] = {}  # provider -> token whose change was announced
        self._usage_sigs: list[str] = []
        versions = {"addon": config.version}
        if probe_versions:
            versions.update(_probe_versions(config.providers))
        self.state = StateStore(config.state_file, config.interval, versions, clock)
        self.state.load_previous()
        if config.check_interval > 0:
            self.state.check = {"enabled": True, "interval": config.check_interval, "last_check_at": None,
                                "result": None, "error_code": None, "triggered_syncs": 0}
        self._last_items: int | None = self.state.items if self.state.last_success_at is not None else None
        self.redactor.register(_env_secrets())

    # ------------------------------------------------------------ Controller

    def trigger_sync(self, force: bool = False) -> bool:
        with self._ctl:
            if self._running or self._pending or self._clock() - self._last_attempt < MANUAL_MIN_GAP:
                return False
            self._pending = True
            self._force = force
        self._wake.set()
        return True

    def preview(self) -> dict[str, Any]:
        out: dict[str, Any] = {"added": [], "removed": [], "changed": [], "errors": []}
        if not self._cycle_lock.acquire(timeout=PREVIEW_WAIT):
            out["errors"].append({"provider": None, "code": "busy", "message": "a sync is running"})
            return out
        try:
            contributions = []
            for name in self.cfg.providers:
                fetched = self._fetch_provider(name)
                if fetched.snapshot is None:
                    out["errors"].append({"provider": name, "code": fetched.code, "message": fetched.message})
                else:
                    contributions.append((name, fetched.snapshot))
            if out["errors"]:
                return out
            try:
                merged = merge(contributions, self.cfg.collision_policy)
            except MergeError as exc:
                out["errors"].append({"provider": None, "code": exc.code, "message": self._clean(str(exc))})
                return out
            try:
                synth = self._synthetic(merged.secrets)
            except SyntheticFailure as exc:
                out["errors"].append({"provider": None, "code": exc.code, "message": str(exc)})
                return out
            merged.secrets.update(synth)
            current = read_secrets(self.cfg.secrets_file) or {}
            added, removed, changed = _diff(current, merged.secrets)
            out.update(added=added, removed=removed, changed=changed)
            if self.cfg.synthetic_keys:
                out["synthetic"] = sorted(synth)
            return out
        finally:
            self._cycle_lock.release()

    # ------------------------------------------------------------ loop

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def run_forever(self) -> None:
        self.state.save()
        while not self._stop.is_set():
            with self._ctl:
                force, self._force = self._force, False
            self.run_once(force=force)
            self._sleep()

    def _sleep(self) -> None:
        """Wait for the next due sync or change probe (whichever is earlier); wake on trigger or stop()."""
        while not self._stop.is_set():
            now = self._clock()
            if now >= self._next_at:
                return
            probe_at = self._next_probe if self.cfg.check_interval > 0 and self._next_probe is not None else None
            if probe_at is not None and now >= probe_at:
                self.run_check()
                if self._pending:
                    self._wake.clear()
                    return
                continue
            remaining = self._next_at - now if probe_at is None else min(self._next_at, probe_at) - now
            if self._wake.wait(min(remaining, HEARTBEAT)):
                self._wake.clear()
                return
            self.state.save()

    def run_check(self) -> None:
        """Probe providers that implement check(); start an early cycle when a source changed. Never raises."""
        now = self._clock()
        self._next_probe = now + self.cfg.check_interval
        try:
            self._probe(now)
        except Exception as exc:  # a probe must never break the loop
            log.warning("change check failed (%s)", type(exc).__name__)
        self.state.save()

    def _probe(self, now: float) -> None:
        check = self.state.check
        if not check.get("enabled"):
            return
        probed = 0
        changed: list[str] = []
        first_error: str | None = None
        for name in self.cfg.providers:
            fn = getattr(self._providers.get(name), "check", None)
            if not callable(fn):
                continue
            try:
                token = fn()
            except ProviderError as exc:
                code, token = exc.code, None
            except Exception as exc:
                code, token = "check_internal_error", None
                log.warning("change check raised %s", type(exc).__name__)
            else:
                code = ""
            if code:
                probed += 1
                first_error = first_error or code
                if self._check_errors.get(name) != code:
                    self._check_errors[name] = code
                    self.state.add_event("warning", "check_failed",
                                         self._clean(f"change check failed for {name}: {code}"), name)
                continue
            if token is None:
                continue
            probed += 1
            self._check_errors.pop(name, None)
            token = str(token)
            stored = self._tokens.get(name)
            if not stored:
                self._tokens[name] = token  # nothing to compare with yet: just remember
            elif token != stored:
                changed.append(name)
                if self._announced.get(name) != token:
                    self._announced[name] = token
                    self.state.add_event("info", "source_changed",
                                         f"{name}: source changed ({stored[:12]} -> {token[:12]})", name)
        check["last_check_at"] = iso(now)
        check["error_code"] = first_error
        if not probed:
            check["result"] = "unsupported"
        elif first_error:
            check["result"] = "error"
        else:
            check["result"] = "changed" if changed else "unchanged"
        # An early cycle waits out backoff (the retry is already scheduled) and honours the manual gap
        if changed and not self._fails and self.trigger_sync():
            check["triggered_syncs"] = check.get("triggered_syncs", 0) + 1

    def run_once(self, force: bool = False) -> str:
        """One full cycle; returns the resulting status."""
        with self._cycle_lock:
            with self._ctl:
                self._running = True
                self._pending = False
                self._last_attempt = self._clock()
            try:
                self._cycle(force)
            except Exception as exc:  # the loop must never die
                log.error("unexpected sync failure (%s)", type(exc).__name__)
                self._finish(self._clock(), "degraded" if self.state.last_success_at else "error",
                             "internal_error", [])
            finally:
                with self._ctl:
                    self._running = False
            return self.state.status

    # ------------------------------------------------------------ cycle

    def _cycle(self, force: bool) -> None:
        st = self.state
        now = self._clock()
        st.last_attempt_at = now
        errors = [p for p in self.cfg.problems if p.severity == "error"]
        if errors:
            sigs = [self._emit("error", p.code, p.message) for p in errors]
            self._finish(now, "error", errors[0].code, sigs)
            return

        st.guard = None
        self._synthetic_report()
        fetches = [self._fetch_provider(name) for name in self.cfg.providers]
        used: list[tuple[str, Snapshot]] = []
        failed: list[_Fetch] = []
        sigs: list[str] = []
        for fetched in fetches:
            if fetched.snapshot is not None:
                self._last_good[fetched.name] = fetched.snapshot
                self._tokens[fetched.name] = fetched.snapshot.check_token
                used.append((fetched.name, fetched.snapshot))
                self._pinfo[fetched.name] = {
                    "status": "ok", "last_success_at": iso(now), "items": len(fetched.snapshot.secrets),
                    "error_code": None, "problems": _problems(fetched.problems),
                    "revision": fetched.snapshot.revision,
                }
                continue
            failed.append(fetched)
            held = self._last_good.get(fetched.name)
            if held is not None and not fetched.collision:
                used.append((fetched.name, held))
            info = self._pinfo.setdefault(fetched.name, {"last_success_at": None, "items": 0, "revision": ""})
            info.update(status="degraded" if held is not None else "error", error_code=fetched.code,
                        problems=_problems(fetched.problems))
            detail = f": {fetched.message}" if fetched.message and fetched.message != fetched.code else ""
            sigs.append(self._emit("error", fetched.code or "provider_error",
                                   f"provider {fetched.name}: {fetched.code}{detail}", fetched.name))
            for problem in fetched.problems or []:
                if problem.severity == "error":
                    sigs.append(self._emit("error", problem.code, problem.message, fetched.name))

        # Provider notices (e.g. an empty filter result) must show up even when the cycle then fails
        for fetched in fetches:
            provider = self._providers.get(fetched.name)
            for level, code, message in getattr(provider, "notices", []) or []:
                sigs.append(self._emit(level, code, message, fetched.name))

        fatal: tuple[str, str] | None = None
        merged: Merged | None = None
        collided = next((f for f in failed if f.collision), None)
        if collided is not None:
            fatal = ("key_collision", collided.message)
        elif any(f.name not in self._last_good for f in failed):
            fatal = (failed[0].code or "provider_error", "provider failed and nothing is held in memory")
        else:
            try:
                merged = merge(used, self.cfg.collision_policy)
            except MergeError as exc:
                fatal = (exc.code, str(exc))
        wrote = False
        files_skipped: list[str] = []
        synth_names: list[str] = []
        if merged is not None and fatal is None and self.cfg.synthetic_keys:
            try:
                synth = self._synthetic(merged.secrets)
                merged.secrets.update(synth)
                synth_names = sorted(synth)
                self._synthetic_report(rendered=True)
            except SyntheticFailure as exc:
                fatal = (exc.code, str(exc))
                self._synthetic_report(failure=exc)
        if merged is not None and fatal is None:
            items = len(merged.secrets)
            if check_shrink(items, self._last_items, self.cfg.shrink_guard_percent, force):
                fatal = ("shrink_guard", f"refusing to write {items} items (last write: {self._last_items})")
                self._guard_report(merged.secrets)
            else:
                try:
                    fres = write_files(self.cfg.files_dir, self.cfg.data_dir / "files.manifest.json", merged.files)
                    files_skipped = fres.skipped
                    previous = self._last_written
                    if previous is None:
                        previous = read_secrets(self.cfg.secrets_file) or {}
                    wrote = write_secrets(self.cfg.secrets_file, merged.secrets)
                    self._after_write(merged, previous, wrote)
                except WriteError as exc:
                    fatal = (exc.code, str(exc))
        if fatal is not None:
            code, message = fatal
            sigs.append(self._emit("error", code, self._clean(message)))
            self._finish(now, "degraded" if st.last_success_at is not None else "error", code, sigs)
            return

        assert merged is not None
        for name, winner, loser in merged.shadowed:
            sigs.append(self._emit("info", "key_shadowed", f"'{name}' from {loser} shadowed by {winner}"))
        for rel in files_skipped:
            sigs.append(self._emit("warning", "file_unmanaged", f"existing unmanaged file '{rel}' not overwritten"))
        st.last_success_at = now
        st.items = len(merged.secrets)
        st.keys["names"] = sorted(merged.secrets)
        if self.cfg.synthetic_keys:
            st.keys["synthetic"] = synth_names
        else:
            st.keys.pop("synthetic", None)
        was_ok = st.status == "ok"
        if failed or files_skipped:
            code = failed[0].code if failed else "file_unmanaged"
            self._finish(now, "degraded", code, sigs)
            return
        if wrote:
            k = st.keys
            st.add_event("info", "sync_ok", f"synced {st.items} items ({len(k['added'])} added, "
                                            f"{len(k['removed'])} removed, {len(k['changed'])} changed)")
        elif not was_ok and st.status != "starting":
            st.add_event("info", "sync_ok", f"sync recovered ({st.items} items)")
        self._finish(now, "ok", None, sigs)

    def _guard_report(self, secrets: Mapping[str, str]) -> None:
        """Names (never values) of what a forced write would change, shown next to the "Apply anyway" button."""
        previous = self._last_written
        if previous is None:
            previous = read_secrets(self.cfg.secrets_file) or {}
        added, removed, changed = _diff(previous, secrets)
        self.state.guard = {"new_items": len(secrets), "last_items": self._last_items,
                            "removed": removed, "added": added, "changed": changed}

    def _synthetic_report(self, rendered: bool = False, failure: SyntheticFailure | None = None) -> None:
        """Per-key status for the UI: names, templates (config, no values), referenced key names, parse/render result."""
        defs = self.cfg.synthetic_keys
        if not defs:
            self.state.synthetic = []
            return
        try:
            from app.engine import synthetic
            entries = synthetic.inspect(defs)
        except ImportError:
            entries = [{"name": n, "template": tpl, "refs": [], "error_code": "synthetic_unavailable"}
                       for n, tpl in defs]
        report = []
        for entry in entries:
            code = entry.pop("error_code")
            if code is None and failure is not None and failure.name == entry["name"]:
                code = failure.code
            entry["status"] = "error" if code else ("ok" if rendered else "pending")
            entry["error_code"] = code
            report.append(entry)
        self.state.synthetic = report

    def _synthetic(self, secrets: Mapping[str, str]) -> dict[str, str]:
        """Render synthetic keys from the merged real keys. Raises SyntheticFailure (code + names only)."""
        if not self.cfg.synthetic_keys:
            return {}
        try:
            from app.engine import synthetic
        except ImportError:
            raise SyntheticFailure("synthetic_unavailable", "synthetic keys need jinja2, which is not installed") \
                from None
        try:
            out = synthetic.apply(secrets, self.cfg.synthetic_keys)
        except synthetic.SyntheticError as exc:
            raise SyntheticFailure(exc.code, str(exc), exc.name) from None
        self.redactor.register(out.values())
        return out

    def _after_write(self, merged: Merged, previous: dict[str, str], wrote: bool) -> None:
        self._last_written = dict(merged.secrets)
        self._last_items = len(merged.secrets)
        if wrote:
            added, removed, changed = _diff(previous, merged.secrets)
            self.state.keys.update(added=added, removed=removed, changed=changed)

    def _finish(self, now: float, status: str, code: str | None, sigs: list[str]) -> None:
        st = self.state
        st.status = status
        st.error_code = code
        self._active = {s for s in sigs if s}
        self._fails = 0 if status == "ok" else self._fails + 1
        delay = self.cfg.interval if not self._fails else min(BACKOFF_START * 2 ** (self._fails - 1),
                                                              self.cfg.interval)
        self._next_at = now + delay
        st.next_sync_at = self._next_at
        if self._next_probe is None and self.cfg.check_interval > 0:
            self._next_probe = now + self.cfg.check_interval
        self._refresh_usage(now)
        for name in self.cfg.providers:
            st.providers[name] = self._pinfo.get(name) or {
                "status": "error", "last_success_at": None, "items": 0, "error_code": code, "problems": [],
            }
        for name in config_mod.PROVIDER_MODULES:
            if name not in self.cfg.providers:
                st.providers[name] = {"status": "disabled", "last_success_at": None, "items": 0,
                                      "error_code": None, "problems": []}
        st.save()
        log.log(logging.INFO if status == "ok" else logging.WARNING, "sync finished: status=%s code=%s items=%d",
                status, code, st.items)

    def _refresh_usage(self, now: float) -> None:
        """Scan YAML files for `!secret` references (names and positions only). Throttled, never raises."""
        if self.cfg.usage_scan == "off":
            return
        self._active.update(self._usage_sigs)  # keeps an unchanged condition from being re-announced
        if self._usage_at is not None and now - self._usage_at < USAGE_MIN_GAP:
            return
        self._usage_at = now
        try:
            known = read_secrets(self.cfg.secrets_file)
            if known is None:
                return
            roots = [("config", self.cfg.secrets_file.parent)]
            if self.cfg.usage_scan == "all":
                roots.append(("addon_configs", self.cfg.addon_configs_dir))
            block = usage_mod.summarize(usage_mod.scan(roots), set(known))
            block["scanned_at"] = iso(now)
            self.state.usage = block
            missing = sorted(block["missing"])  # type: ignore[arg-type]
            if missing:
                self._usage_sigs = [self._emit("warning", "secret_missing", "referenced but not in secrets.yaml: "
                                               + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))]
            else:
                self._usage_sigs = []
            self._active.update(self._usage_sigs)
        except Exception as exc:  # diagnostics must never break the sync
            log.warning("usage scan failed (%s)", type(exc).__name__)

    def _emit(self, level: str, code: str, message: str, provider: str | None = None) -> str:
        """Add an event once per active condition; returns the dedupe signature."""
        sig = f"{provider}:{code}:{message}"
        if sig not in self._active:
            self.state.add_event(level, code, self._clean(message), provider)
            getattr(log, "warning" if level != "info" else "info")("%s", self._clean(f"{code}: {message}"))
        return sig

    def _clean(self, text: str) -> str:
        return self.redactor.scrub(text)

    # ------------------------------------------------------------ providers

    def _provider(self, name: str) -> Provider:
        if name not in self._providers:
            self._providers[name] = config_mod.load_provider(name, self.cfg.provider_cfg.get(name, {}))
        return self._providers[name]

    def _fetch_provider(self, name: str) -> _Fetch:
        try:
            provider = self._provider(name)
        except ProviderLoadError as exc:
            return _Fetch(name, None, exc.code, str(exc), [Problem(exc.code, str(exc))])
        try:
            problems = list(provider.validate(self.cfg.provider_cfg.get(name, {})))
        except Exception as exc:
            problems = [Problem("validate_failed", f"validate raised {type(exc).__name__}")]
        blocking = [p for p in problems if p.severity == "error"]
        if blocking:
            return _Fetch(name, None, blocking[0].code, blocking[0].message, problems)
        try:
            snap = provider.fetch()
        except ProviderError as exc:
            return _Fetch(name, None, exc.code, self._clean(str(exc)), problems, exc.code == "key_collision")
        except Exception as exc:
            return _Fetch(name, None, "provider_internal_error", f"unexpected {type(exc).__name__}", problems)
        self.redactor.register(snap.secrets.values())
        return _Fetch(name, snap, None, "", problems)


def _problems(problems: list[Problem] | None) -> list[dict[str, str]]:
    return [{"code": p.code, "message": p.message, "severity": p.severity} for p in problems or []]


def _diff(old: Mapping[str, str], new: Mapping[str, str]) -> tuple[list[str], list[str], list[str]]:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(new) & set(old) if new[k] != old[k])
    return added, removed, changed


def _env_secrets() -> list[str]:
    import os

    return [os.environ[k] for k in ("BW_CLIENTSECRET", "BW_PASSWORD", "BW_CLIENTID") if os.environ.get(k)]


def _probe_versions(providers: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in providers:
        tool = TOOLS.get(name)
        if not tool:
            continue
        try:
            cp = subprocess.run([tool, "--version"], capture_output=True, timeout=10, check=False, text=True,
                                stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"\d+(?:\.\d+)+", cp.stdout or "")
        if match:
            out[tool] = match.group()
    return out
