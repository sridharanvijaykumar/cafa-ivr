#!/usr/bin/env python3
"""Generate RELEASE_MANIFEST.sha256 from repository release files."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.sha256"
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", "build", "dist"}


def release_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if relative.name == MANIFEST.name or EXCLUDED_PARTS.intersection(relative.parts):
            continue
        if (ROOT / relative).is_file() and not any(
            part.endswith(".egg-info") for part in relative.parts
        ):
            paths.append(relative)
    return sorted(paths, key=lambda path: path.as_posix())


def main() -> None:
    lines = []
    for relative in release_files():
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{relative.as_posix()}")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(lines)} entries to {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
