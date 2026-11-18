"""Every file location the add-on uses, in one place (contract for all modules and later phases)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

HTTP_PORT: int = 8080


@dataclass(frozen=True)
class Paths:
    """File locations; production uses `default()`, tests use `under(tmp_path)`."""

    data_dir: Path
    options_file: Path
    access_file: Path
    status_file: Path
    repos_root: Path
    access_root: Path
    run_dir: Path
    lock_file: Path
    trigger_file: Path
    gitconfig_file: Path
    supervisor_state_file: Path
    supervisor_requests_dir: Path

    @classmethod
    def _build(cls, data_dir: Path, srv_git: Path, run_dir: Path, gitconfig_file: Path) -> "Paths":
        return cls(
            data_dir=data_dir,
            options_file=data_dir / "options.json",
            access_file=data_dir / "access.json",
            status_file=data_dir / "status.json",
            repos_root=srv_git / "repos",
            access_root=srv_git / "access",
            run_dir=run_dir,
            lock_file=run_dir / "access.lock",
            trigger_file=run_dir / "sync.request",
            gitconfig_file=gitconfig_file,
            supervisor_state_file=data_dir / "supervisor.json",
            supervisor_requests_dir=run_dir / "supervisor.requests",
        )

    @classmethod
    def default(cls) -> "Paths":
        """Production layout. No environment overrides: nothing in production may move these paths."""
        return cls._build(
            Path("/data"), Path("/srv/git"), Path("/run/marketplace-repo-proxy"), Path("/etc/gitconfig")
        )

    @classmethod
    def under(cls, root: Path | str) -> "Paths":
        """Same layout below `root` (tests)."""
        base = Path(root)
        return cls._build(base / "data", base / "srv" / "git", base / "run", base / "etc" / "gitconfig")

    def repo_dir(self, owner: str, name: str) -> Path:
        return self.repos_root / owner / f"{name}.git"

    def link_path(self, owner: str, name: str, hash_: str) -> Path:
        return self.access_root / owner / name / hash_
