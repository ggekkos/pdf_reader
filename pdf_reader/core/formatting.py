"""Friendly text for the interface."""

from __future__ import annotations

import time


def time_ago(moment: float, now: float | None = None) -> str:
    """E.g. "just now", "5 min ago", "yesterday", "3 days ago"."""
    now = time.time() if now is None else now
    seconds = max(now - moment, 0)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86_400:
        return f"{int(seconds // 3600)} h ago"
    days = int(seconds // 86_400)
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    return time.strftime("%b %d, %Y", time.localtime(moment))


def duration(minutes: float) -> str:
    """E.g. "under 1 min", "12 min", "1 h 05 min", "3 h"."""
    if minutes < 1:
        return "under 1 min"
    total = round(minutes)
    if total < 60:
        return f"{total} min"
    hours, rest = divmod(total, 60)
    return f"{hours} h {rest:02d} min" if rest else f"{hours} h"
