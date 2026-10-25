"""Defensive coercion and provider-neutral derived fields shared by both sources."""

import math
from datetime import datetime
from typing import Any


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())[:200]


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _display(value: int | float | None) -> str:
    return "--" if value is None else f"{value:.0f}"


def _mapping(value: Any) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected a profile object")
    return value


def _sequence(value: Any) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Expected a profile list")
    return value


def derived(runs: list, raids: list, updated: str, now: datetime) -> dict:
    """Weekly key, raid and freshness fields, identical for every provider."""
    runs.sort(key=lambda r: r["level"], reverse=True)
    age = None
    if updated:
        try:
            parsed = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            age = max(0, int((now - parsed).total_seconds() // 86400))
        except (ValueError, TypeError):
            pass
    highest = runs[0]["level"] if runs else None
    timed = max((r["level"] for r in runs if r["timed"]), default=None)
    return {
        "weekly_highest_key": highest, "weekly_highest_timed_key": timed,
        "weekly_key_display": "--" if highest is None else f"+{highest:g}",
        "weekly_runs": runs, "raids": raids,
        "raid_progress": " | ".join(r["summary"] for r in raids) or "NO DATA",
        "source_updated_at": updated, "source_updated_date": updated[:10] or "UNKNOWN",
        "source_age_days": age, "fetched_at": now.isoformat(),
        "stale": False, "status": "OLD DATA" if age is not None and age > 7 else "OK",
    }
