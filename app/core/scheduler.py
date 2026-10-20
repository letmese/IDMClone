"""Scheduler + traffic quota — IDM Pro scheduler (start/stop windows, speed caps) and quota."""
from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings, CONFIG_PATH


@dataclass
class ScheduleEntry:
    name: str = ""
    start: str = "22:00"              # "HH:MM"
    end: str = ""                     # "HH:MM", empty = no stop
    days: set = field(default_factory=lambda: {0, 1, 2, 3, 4, 5, 6})  # ISO weekdays
    action: str = "start_all"         # start_all | stop_all | limit_speed
    limit_kbps: int = 0

    def to_dict(self):
        return {"name": self.name, "start": self.start, "end": self.end,
                "days": sorted(self.days), "action": self.action, "limit_kbps": self.limit_kbps}

    @classmethod
    def from_dict(cls, d):
        return cls(name=d.get("name", ""), start=d.get("start", "22:00"), end=d.get("end", ""),
                   days=set(d.get("days", [0, 1, 2, 3, 4, 5, 6])), action=d.get("action", "start_all"),
                   limit_kbps=d.get("limit_kbps", 0))


class Scheduler:
    def __init__(self, settings: Settings, on_apply=None):
        self.settings = settings
        self.on_apply = on_apply  # callback(action, limit_kbps)
        self._last_check = None
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading_thread(self._loop)
            self._thread.start()

    def _loop(self):
        while True:
            time.sleep(15)
            self.check()

    def check(self) -> bool:
        """Returns True if an action fired this check. Called by UI too."""
        if not self.settings.schedule_enabled:
            return False
        now = dt.datetime.now()
        key = (now.strftime("%Y-%m-%d %H:%M"),)
        if key == self._last_check:
            return False
        self._last_check = key
        fired = False
        for d in self.settings.schedule_entries:
            e = ScheduleEntry.from_dict(d)
            if now.weekday() not in e.days:
                continue
            cur = now.strftime("%H:%M")
            if e.start <= cur and (not e.end or cur <= e.end):
                if self.on_apply:
                    self.on_apply(e.action, e.limit_kbps)
                fired = True
        return fired


def threading_thread(target):
    import threading
    t = threading.Thread(target=target, daemon=True)
    return t


class Quota:
    """Monthly/weekly traffic quota. Records bytes and can stop queue when exhausted."""

    def __init__(self, settings: Settings, on_exhaust=None):
        self.settings = settings
        self.on_exhaust = on_exhaust
        self._file = CONFIG_PATH.parent / "quota.json"
        self._data = self._load()

    def _load(self):
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self._data), encoding="utf-8")

    def _period_key(self) -> str:
        now = dt.datetime.now()
        if self.settings.quota_period == "weekly":
            iso = now.isocalendar()
            return f"w{iso[0]}-{iso[1]}"
        return f"m{now.year}-{now.month}"

    def add(self, nbytes: int) -> None:
        if not self.settings.quota_enabled or nbytes <= 0:
            return
        key = self._period_key()
        self._data[key] = self._data.get(key, 0) + nbytes
        self._save()
        if self._data[key] >= self.settings.quota_bytes and self.on_exhaust:
            self.on_exhaust()

    def used(self) -> int:
        if not self.settings.quota_enabled:
            return 0
        return self._data.get(self._period_key(), 0)

    def remaining(self) -> int:
        if not self.settings.quota_enabled:
            return -1
        return max(0, self.settings.quota_bytes - self.used())
