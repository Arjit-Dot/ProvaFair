"""Run folders: data/runs/<service>/<run_id>/ (override the root with PROVAFAIR_DATA)."""
import json
import os
import re
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data" / "runs"
_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


def root() -> Path:
    return Path(os.getenv("PROVAFAIR_DATA", DEFAULT_ROOT))


def run_dir(service: str, run_id: str, create: bool = False) -> Path:
    if not _SAFE.match(service) or not _SAFE.match(run_id):
        raise ValueError("invalid service or run id")
    d = root() / service / run_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(d: Path, name: str, obj) -> None:
    (Path(d) / name).write_text(json.dumps(obj, indent=2, sort_keys=True))


def read_json(d: Path, name: str):
    return json.loads((Path(d) / name).read_text())


def exists(d: Path, name: str) -> bool:
    return (Path(d) / name).exists()


def list_runs(service: str) -> list[dict]:
    base = root() / service
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if (d / "receipt.json").exists():
                out.append(read_json(d, "receipt.json"))
    return sorted(out, key=lambda r: r["finalized"], reverse=True)
