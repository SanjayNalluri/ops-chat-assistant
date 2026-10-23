"""Read KEY=VALUE lines from a local .env file into the environment (no extra package)."""
import os
from pathlib import Path


def load_env(path: Path = Path(__file__).resolve().parents[1] / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
