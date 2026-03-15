from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path


def save_report(report: object, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(asdict(report), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_report(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
