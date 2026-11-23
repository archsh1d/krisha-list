"""Persisted source cooldown shared by the web collector and CLI."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


SOURCE_COOLDOWN = timedelta(minutes=30)
MAX_SOURCE_COOLDOWN = timedelta(hours=4)


def source_retry_at(access: dict | None, consecutive_failures: int = 1) -> datetime | None:
    if not access or not access["finished_at"] or not (
        access["source_status"] in (403, 429, 468) or
        (access["source_status"] == 200 and access["status"] == "blocked")
    ):
        return None
    finished = datetime.fromisoformat(access["finished_at"])
    multiplier = 2 ** min(max(consecutive_failures - 1, 0), 3)
    retry_at = finished + min(SOURCE_COOLDOWN * multiplier, MAX_SOURCE_COOLDOWN)
    snapshot_dir = access.get("snapshot_dir")
    if snapshot_dir:
        try:
            saved = json.loads((Path(snapshot_dir) / "source-error.json").read_text(encoding="utf-8"))
            value = saved.get("response", {}).get("retry_after")
            if isinstance(value, str) and value.strip():
                suggested = finished + timedelta(seconds=int(value)) if value.isdecimal() else parsedate_to_datetime(value)
                if suggested.tzinfo is None:
                    suggested = suggested.replace(tzinfo=timezone.utc)
                retry_at = max(retry_at, suggested)
        except (OSError, ValueError, TypeError, OverflowError, AttributeError):
            pass
    return retry_at
