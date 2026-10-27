import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))



@pytest.fixture
def age_key(tmp_path: Path) -> tuple[Path, str]:
    key = tmp_path / "age.key"
    subprocess.run(["age-keygen", "-o", str(key)], check=True, capture_output=True)
    key.chmod(0o600)
    pub = next(ln for ln in key.read_text().splitlines() if ln.startswith("# public key:")).split(": ")[1]
    return key, pub


@pytest.fixture
def encrypt(tmp_path: Path, age_key):
    def _encrypt(plain: str, name: str = "secrets.sops.yaml") -> Path:
        src = tmp_path / "plain.yaml"
        src.write_text(plain)
        out = tmp_path / name
        res = subprocess.run(
            ["sops", "--encrypt", "--age", age_key[1], "--input-type", "yaml", "--output-type", "yaml", str(src)],
            check=True,
            capture_output=True,
        )
        out.write_bytes(res.stdout)
        src.unlink()
        return out

    return _encrypt
