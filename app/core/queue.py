"""Download queue — IDM queue/priority behavior."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from ..config import Settings, CONFIG_PATH


class DownloadQueue:
    def __init__(self, settings: Settings, on_change=None):
        self.settings = settings
        self.tasks = []
        self._lock = threading.Lock()
        self._on_change = on_change
        self._running = set()
        self._monitor = threading.Thread(target=self._loop, daemon=True)
        self._monitor.start()
        self._load()

    def _path(self):
        return CONFIG_PATH.parent / "queue.json"

    def _load(self):
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                from ..engine.downloader import DownloadTask
                for d in data:
                    t = DownloadTask(url=d["url"], dest_dir=d["dest_dir"], filename=d.get("filename", ""),
                                     category=d.get("category", "Other"), settings=self.settings,
                                     segments=d.get("segments", self.settings.max_connections))
                    t.state = d.get("state", "queued")
                    t.file_path = d.get("file_path", "")
                    t.total_size = d.get("total", 0)
                    t.queue_name = d.get("queue_name", "Main Queue")
                    self.tasks.append(t)
            except Exception:
                pass

    def _save(self):
        try:
            self._path().write_text(json.dumps(
                [{"url": t.url, "dest_dir": t.dest_dir, "filename": t.filename, "category": t.category,
                  "segments": t.segments, "state": t.state, "file_path": t.file_path, "total": t.total_size,
                  "queue_name": getattr(t, "queue_name", "Main Queue")}
                 for t in self.tasks], indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def add(self, task) -> None:
        with self._lock:
            task.on_update = self._on_change
            self.tasks.append(task)
            self._save()
        if self._on_change:
            self._on_change(task)
        # A newly added task must start automatically (respecting the
        # concurrent-task limit) instead of sitting in "queued" forever.
        self._kick()

    def start_all(self) -> None:
        self._kick()

    def pause(self, task) -> None:
        task.pause()
        self._save()

    def resume(self, task) -> None:
        task.state = "running"
        with self._lock:
            if task not in self._running:
                self._running.add(task)
        task.start()

    def remove(self, task, delete_files: bool = False) -> None:
        task.cancel()
        if delete_files and task.file_path and Path(task.file_path).exists():
            try:
                Path(task.file_path).unlink()
            except OSError:
                pass
        with self._lock:
            if task in self.tasks:
                self.tasks.remove(task)
        self._save()

    def _kick(self) -> None:
        to_start = []
        with self._lock:
            if len(self._running) >= self.settings.max_concurrent_tasks:
                return
            for t in self.tasks:
                if t.state in ("queued", "running") and t not in self._running:
                    if getattr(t, "queue_name", "Main Queue") == "Night Owl Queue" and not getattr(self.settings, "night_owl_enabled", False):
                        continue
                    if len(self._running) >= self.settings.max_concurrent_tasks:
                        break
                    self._running.add(t)
                    if t.state == "queued":
                        t.state = "running"
                    to_start.append(t)
        # Start outside the lock: task.start() performs a network probe and
        # must not block the queue (add/save/pause) for up to the probe timeout.
        for t in to_start:
            t.start()

    def _loop(self) -> None:
        while True:
            time.sleep(1.0)
            changed = False
            with self._lock:
                finished = [t for t in self._running if t.state in ("completed", "error", "paused")]
                for t in finished:
                    self._running.discard(t)
                    changed = True
                if changed:
                    self._save()
            self._kick()
