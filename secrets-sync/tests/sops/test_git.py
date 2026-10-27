import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.providers import gitsource
from app.providers.base import ProviderError
from app.providers.sops import Provider

pytestmark = pytest.mark.skipif(
    not (shutil.which("sops") and shutil.which("age-keygen") and shutil.which("git")),
    reason="sops, age-keygen and git are not installed",
)

PLAIN = "api_key: s3cr3t-git-ONE\ndb:\n  pass: s3cr3t-git-TWO\n"
TOKEN = "tok-s3cr3t-TOKEN-value"


def git(*args, cwd=None):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path, age_key, monkeypatch):
    """Bare repo with an encrypted file on `main`; returns helper object."""
    monkeypatch.setenv("SS_GIT_ALLOW_PROTOCOL", "file")
    monkeypatch.setenv("SS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SS_AGE_KEY_FILE", str(age_key[0]))
    bare = tmp_path / "remote.git"
    work = tmp_path / "work"
    git("init", "--bare", "-b", "main", str(bare))
    git("init", "-b", "main", str(work))
    git("remote", "add", "origin", str(bare), cwd=work)

    class Repo:
        url = str(bare)

        def commit(self, plain: str, rel: str = "secrets.sops.yaml") -> None:
            src = tmp_path / "plain.yaml"
            src.write_text(plain)
            res = subprocess.run(
                ["sops", "--encrypt", "--age", age_key[1], "--input-type", "yaml", "--output-type", "yaml", str(src)],
                check=True,
                capture_output=True,
            )
            src.unlink()
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(res.stdout)
            git("add", "-A", cwd=work)
            git("commit", "-m", "update", cwd=work)
            git("push", "origin", "main", cwd=work)

    r = Repo()
    r.work = work
    r.commit(PLAIN)
    return r


def prov(url, **kw):
    cfg = {"source": "git", "git_url": url, "git_branch": "main", "git_path": "secrets.sops.yaml"}
    cfg.update(kw)
    return Provider(cfg)


def test_fetch_check_and_change(repo):
    p = prov(repo.url)
    assert p.validate({}) == []
    token = p.check()
    snap = p.fetch()
    assert snap.secrets == {"api_key": "s3cr3t-git-ONE", "db_pass": "s3cr3t-git-TWO"}
    assert snap.check_token == token and len(token) == 40
    assert snap.revision == token[:12]

    # unchanged: second fetch uses the fetch/reset path
    assert p.fetch().check_token == token

    repo.commit("api_key: changed-value\n")
    token2 = p.check()
    assert token2 != token
    snap2 = p.fetch()
    assert snap2.secrets == {"api_key": "changed-value"}
    assert snap2.check_token == token2


def test_broken_cache_is_recloned(repo, tmp_path):
    p = prov(repo.url)
    p.fetch()
    cache = next((tmp_path / "data" / "git").iterdir())
    shutil.rmtree(cache / ".git" / "objects")
    assert p.fetch().secrets["api_key"] == "s3cr3t-git-ONE"


def test_nested_path(repo):
    repo.commit("k: v\n", rel="a/b/s.sops.yaml")
    assert prov(repo.url, git_path="a/b/s.sops.yaml").fetch().secrets == {"k": "v"}


def test_file_source_has_no_check(age_key, encrypt):
    assert Provider({"file": str(encrypt(PLAIN)), "age_key_file": str(age_key[0])}).check() is None


def test_branch_not_found(repo):
    p = prov(repo.url, git_branch="nope")
    for call in (p.check, p.fetch):
        with pytest.raises(ProviderError) as e:
            call()
        assert e.value.code == "git_ref_not_found"


def test_file_missing_in_repo(repo):
    with pytest.raises(ProviderError) as e:
        prov(repo.url, git_path="other.yaml").fetch()
    assert e.value.code == "git_file_missing"


@pytest.mark.parametrize("bad", ["../x.yaml", "a/../../x", "/etc/passwd", "a\\b", "a/../b"])
def test_path_traversal_rejected(repo, bad):
    p = prov(repo.url, git_path=bad)
    assert "sops_git_path_invalid" in {x.code for x in p.validate({})}
    with pytest.raises(ProviderError):
        p.fetch()


def test_symlink_outside_rejected(repo, tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("sops: {}\nx: y\n")
    os.symlink(outside, repo.work / "link.yaml")
    os.symlink(tmp_path, repo.work / "dirlink")
    git("add", "-A", cwd=repo.work)
    git("commit", "-m", "links", cwd=repo.work)
    git("push", "origin", "main", cwd=repo.work)
    for path in ("link.yaml", "dirlink/outside.yaml"):
        with pytest.raises(ProviderError) as e:
            prov(repo.url, git_path=path).fetch()
        assert e.value.code == "git_path_invalid"


@pytest.mark.parametrize(
    "url", ["https://user:pw@example.com/r.git", "https://tok@example.com/r.git", "ssh://git:pw@example.com/r.git"]
)
def test_url_credentials_rejected(repo, url):
    p = prov(url)
    assert "sops_git_url_credentials" in {x.code for x in p.validate({})}
    with pytest.raises(ProviderError) as e:
        p.fetch()
    assert e.value.code == "sops_invalid_config"
    with pytest.raises(ProviderError):
        p.check()
    assert "pw" not in str(e.value)


def test_url_scheme_and_validate(monkeypatch):
    monkeypatch.delenv("SS_GIT_ALLOW_PROTOCOL", raising=False)

    def codes(**kw):
        return {x.code for x in prov("", **kw).validate({})}

    assert codes() == {"sops_git_missing_url"}
    for good in ("git@github.com:org/repo.git", "ssh://git@host/org/repo.git", "https://host/org/repo.git"):
        assert prov(good).validate({}) == [], good
    for bad in ("ftp://host/r", "http://host/r", "file:///tmp/r", "/tmp/r", "ext::sh -c id", "-oProxy=x", "host:r"):
        assert {x.code for x in prov(bad).validate({})} == {"sops_git_url_scheme"}, bad
    assert "sops_git_branch_invalid" in {x.code for x in prov("https://h/r", git_branch="-x").validate({})}
    assert {x.code for x in Provider({"source": "svn"}).validate({})} == {"sops_invalid_source"}
    assert Provider({"source": "file", "file": "/x"}).validate({}) == []


@pytest.fixture
def fake_git(tmp_path, monkeypatch):
    """Fake `git` first on PATH; behaviour from the `mode` file, calls logged next to it (the child env is minimal)."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    script = bindir / "git"
    script.write_text(
        "#!/bin/sh\n"
        'd=$(dirname "$0")\n'
        'printf "%s\\n" "$*" >> "$d/git.log"\n'
        'env >> "$d/git.log.env"\n'
        'case "$(cat "$d/mode")" in\n'
        f'  auth) echo "fatal: Authentication failed for {TOKEN}" >&2; exit 128 ;;\n'
        '  denied) echo "git@host: Permission denied (publickey)." >&2; exit 128 ;;\n'
        '  hang) sleep 5 ;;\n'
        '  ok) printf "%s\\trefs/heads/main\\n" 0123456789abcdef0123456789abcdef01234567 ;;\n'
        f'  *) echo "fatal: boom {TOKEN}" >&2; exit 1 ;;\n'
        "esac\n"
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("SS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("SS_GIT_ALLOW_PROTOCOL", raising=False)
    monkeypatch.setenv("SS_GIT_TOKEN", TOKEN)

    class Fake:
        def mode(self, value: str) -> None:
            (bindir / "mode").write_text(value)

        log = bindir / "git.log"
        env = bindir / "git.log.env"

    return Fake()


@pytest.mark.parametrize(
    "mode,code", [("auth", "git_auth_failed"), ("denied", "git_auth_failed"), ("other", "git_fetch_failed")]
)
def test_error_mapping_never_leaks_token(fake_git, monkeypatch, caplog, mode, code):
    fake_git.mode(mode)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ProviderError) as e:
        prov("https://example.com/org/r.git", git_username="bot").check()
    assert e.value.code == code
    assert TOKEN not in str(e.value) and TOKEN not in repr(e.value) and e.value.__cause__ is None
    assert TOKEN not in caplog.text
    argv_log = fake_git.log.read_text()
    assert TOKEN not in argv_log and "bot" not in argv_log
    env_log = fake_git.env.read_text()
    assert f"SS_GIT_TOKEN={TOKEN}" in env_log and "SS_GIT_USERNAME=bot" in env_log
    assert "GIT_ASKPASS=" in env_log and "GIT_TERMINAL_PROMPT=0" in env_log
    assert "GIT_ALLOW_PROTOCOL=ssh:https" in env_log


def test_clone_error_mapping(fake_git, monkeypatch):
    fake_git.mode("other")
    with pytest.raises(ProviderError) as e:
        prov("https://example.com/r.git")._git().sync()
    assert e.value.code == "git_clone_failed"


def test_timeout(fake_git, monkeypatch):
    fake_git.mode("hang")
    monkeypatch.setattr(gitsource, "LS_REMOTE_TIMEOUT", 0.3)
    with pytest.raises(ProviderError) as e:
        prov("https://example.com/r.git").check()
    assert e.value.code == "git_timeout"


def test_fake_probe_ok_and_env_hygiene(fake_git, monkeypatch):
    fake_git.mode("ok")
    monkeypatch.setenv("BW_PASSWORD", "bw-s3cr3t")
    assert prov("https://example.com/r.git").check() == "0123456789abcdef0123456789abcdef01234567"
    log = fake_git.log.read_text()
    assert "ls-remote -- https://example.com/r.git refs/heads/main" in log
    assert "core.hooksPath=/dev/null" in log
    assert "bw-s3cr3t" not in fake_git.env.read_text()


def test_ssh_key_checks(fake_git, monkeypatch, tmp_path):
    fake_git.mode("ok")
    monkeypatch.setattr(gitsource, "ADDON_KNOWN_HOSTS", tmp_path / "no-known-hosts")
    key = tmp_path / "deploy_key"
    monkeypatch.setenv("SS_GIT_DEPLOY_KEY", str(key))
    p = prov("git@example.com:org/r.git")
    with pytest.raises(ProviderError) as e:
        p.check()
    assert e.value.code == "git_key_missing"
    key.write_text("PRIVATE-KEY-MATERIAL")
    key.chmod(0o644)
    with pytest.raises(ProviderError) as e:
        p.check()
    assert e.value.code == "git_key_permissions" and "PRIVATE" not in str(e.value)
    key.chmod(0o600)
    assert p.check()
    env_log = fake_git.env.read_text()
    ssh_line = next(ln for ln in env_log.splitlines() if ln.startswith("GIT_SSH_COMMAND="))
    assert "IdentitiesOnly=yes" in ssh_line and "BatchMode=yes" in ssh_line
    assert "StrictHostKeyChecking=accept-new" in ssh_line and str(key) in ssh_line
    assert "PRIVATE-KEY-MATERIAL" not in env_log


def test_ssh_known_hosts_strict_when_provided(fake_git, monkeypatch, tmp_path):
    fake_git.mode("ok")
    kh = tmp_path / "known_hosts_addon"
    kh.write_text("example.com ssh-ed25519 AAAA\n")
    monkeypatch.setattr(gitsource, "ADDON_KNOWN_HOSTS", kh)
    key = tmp_path / "k"
    key.write_text("x")
    key.chmod(0o600)
    monkeypatch.setenv("SS_GIT_DEPLOY_KEY", str(key))
    prov("ssh://git@example.com/r.git").check()
    env_log = fake_git.env.read_text()
    assert "StrictHostKeyChecking=yes" in env_log and str(kh) in env_log
    assert "SS_GIT_TOKEN" not in env_log  # ssh urls never get the https token


def test_askpass_script(tmp_path):
    ap = gitsource.ASKPASS
    assert os.access(ap, os.X_OK)
    env = {"SS_GIT_TOKEN": TOKEN, "SS_GIT_USERNAME": "bot", "PATH": os.environ["PATH"]}

    def ask(prompt):
        return subprocess.run([str(ap), prompt], env=env, capture_output=True, text=True, check=True).stdout.strip()

    assert ask("Username for 'https://x': ") == "bot"
    assert ask("Password for 'https://bot@x': ") == TOKEN


def test_sops_child_env_has_no_git_credentials(repo, monkeypatch):
    seen = {}
    real_run = subprocess.run

    def spy(argv, *a, **kw):
        if argv and argv[0] == "sops":
            seen.update(kw["env"])
        return real_run(argv, *a, **kw)

    monkeypatch.setenv("SS_GIT_TOKEN", TOKEN)
    monkeypatch.setattr(subprocess, "run", spy)
    assert prov(repo.url).fetch().secrets
    assert seen and not [k for k in seen if k.startswith(("BW_", "SS_GIT_"))]


def test_no_secret_in_logs_for_git_fetch(repo, caplog):
    caplog.set_level(logging.DEBUG)
    prov(repo.url).fetch()
    assert "s3cr3t" not in caplog.text


def test_default_ssh_command_quotes(tmp_path):
    assert gitsource._quote("a b'c") == "'a b'\\''c'"
    assert Path(gitsource.__file__).exists()
