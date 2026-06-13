"""Hermes-compatible schedule parsing and next-run computation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class ScheduleSpec:
    kind: str  # delay | interval | cron | at
    expr: str
    display: str
    interval_seconds: float | None = None


_RELATIVE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_INTERVAL = re.compile(r"^every\s+(\d+)\s*([smhd])$", re.IGNORECASE)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_seconds(amount: int, unit: str) -> float:
    unit = unit.lower()
    if unit == "s":
        return float(amount)
    if unit == "m":
        return float(amount * 60)
    if unit == "h":
        return float(amount * 3600)
    if unit == "d":
        return float(amount * 86400)
    raise ValueError(f"unsupported duration unit: {unit}")


def parse_schedule(text: str) -> ScheduleSpec:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("schedule is required")

    interval_match = _INTERVAL.match(raw)
    if interval_match:
        seconds = _duration_seconds(int(interval_match.group(1)), interval_match.group(2))
        return ScheduleSpec(kind="interval", expr=raw, display=raw, interval_seconds=seconds)

    relative_match = _RELATIVE.match(raw)
    if relative_match:
        seconds = _duration_seconds(int(relative_match.group(1)), relative_match.group(2))
        return ScheduleSpec(kind="delay", expr=raw, display=raw, interval_seconds=seconds)

    if "T" in raw and raw[0].isdigit():
        return ScheduleSpec(kind="at", expr=raw, display=raw)

    parts = raw.split()
    if len(parts) == 5:
        return ScheduleSpec(kind="cron", expr=raw, display=raw)

    raise ValueError(f"unsupported schedule format: {text}")


def _field_matches(field: str, value: int, *, minimum: int, maximum: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return value % step == 0
    for token in field.split(","):
        if "-" in token:
            start, end = token.split("-", 1)
            if int(start) <= value <= int(end):
                return True
        elif int(token) == value:
            return True
    return False


def _next_cron(expr: str, after: datetime) -> datetime:
    minute_f, hour_f, dom_f, month_f, dow_f = expr.split()
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(525600):
        if (
            _field_matches(minute_f, candidate.minute, minimum=0, maximum=59)
            and _field_matches(hour_f, candidate.hour, minimum=0, maximum=23)
            and _field_matches(dom_f, candidate.day, minimum=1, maximum=31)
            and _field_matches(month_f, candidate.month, minimum=1, maximum=12)
            and _field_matches(dow_f, candidate.weekday(), minimum=0, maximum=6)
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError(f"could not find next run for cron expression: {expr}")


def compute_next_run(spec: ScheduleSpec, *, after: datetime | None = None) -> datetime:
    base = after or _utc_now()
    if spec.kind in {"delay", "interval"}:
        assert spec.interval_seconds is not None
        return base + timedelta(seconds=spec.interval_seconds)
    if spec.kind == "at":
        target = datetime.fromisoformat(spec.expr.replace("Z", "+00:00"))
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return target
    if spec.kind == "cron":
        return _next_cron(spec.expr, base)
    raise ValueError(f"unsupported schedule kind: {spec.kind}")


def format_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
