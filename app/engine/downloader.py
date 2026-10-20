"""Segmented download engine — custom implementation of IDMan.exe's core.

Features re-implemented from the decompiled dump:
- N simultaneous Range connections per file (MaxConnectionsNumber)
- Part temp files (<name>.part.<i>) + per-download state JSON for resume
- Join parts into final file when all segments done
- Retries with backoff (mAttempts)
- Disk-space preflight with fallback to temp drive
- Global speed limiter (token bucket, psnSpeedLimit)
- Proxy / SOCKS support, per-site auth, custom headers
- Centralized error strings (mirrors FUN_004ec770)
"""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import requests

from ..config import Settings

# Centralized error strings (IDM keeps these in one place too — FUN_004ec770)
ERRORS = {
    "host": "Cannot resolve host name",
    "connect": "Connection failed: target machine actively refused it",
    "timeout": "Connection timed out",
    "http": "Invalid server response (HTTP {code})",
    "no_range": "Server does not support resume / segmented download",
    "no_length": "Server did not report file size",
    "disk": "Not enough disk space (need {need} MB, have {have} MB)",
    "write": "Cannot write to disk (drive may be full or permission denied)",
    "auth": "Authorization is required for this site/path",
    "ssl": "SSL/TLS handshake failed",
    "aborted": "Download aborted by user",
    "unknown": "Unknown download error",
}

CHUNK = 1 << 16  # 64 KiB read chunks


class SpeedLimiter:
    """Global token-bucket limiter shared by all segments (psnSpeedLimit)."""

    def __init__(self, kbps: int = 0):
        self.kbps = kbps
        self._lock = threading.Lock()
        self._tokens = 0.0
        self._last = time.monotonic()

    def set_limit(self, kbps: int) -> None:
        with self._lock:
            self.kbps = max(0, kbps)
            self._tokens = min(self._tokens, self.kbps * 1024)

    def acquire(self, nbytes: int) -> None:
        """Block until nbytes are available under the current cap."""
        while True:
            with self._lock:
                if self.kbps <= 0:
                    return
                now = time.monotonic()
                self._tokens = max(0.0, self._tokens + (now - self._last) * self.kbps * 1024)
                self._last = now
                if self._tokens >= nbytes:
                    self._tokens -= nbytes
                    return
                deficit = nbytes - self._tokens
                wait = deficit / (self.kbps * 1024)
            time.sleep(min(wait, 0.25))


@dataclass
class PartState:
    index: int
    start: int
    end: int          # inclusive; -1 = open ended
    downloaded: int = 0
    done: bool = False
    speed: float = 0.0
    status: str = "pending"  # pending | streaming | buffered | done | error
    last_bytes: int = 0
    last_tick: float = 0.0


@dataclass
class DownloadTask:
    __hash__ = object.__hash__  # keep tasks hashable (dataclass eq=True sets __hash__=None)
    url: str
    dest_dir: str
    filename: str = ""
    category: str = "Other"
    segments: int = 8
    headers: dict = field(default_factory=dict)
    referer: str = ""
    cookies: dict = field(default_factory=dict)
    auth: Optional[tuple] = None          # (user, pass) for this site
    site: str = ""                        # site key for site_passwords lookup
    speed_limit_kbps: int = 0             # per-task override (0 = global)
    queue_name: str = "Main Queue"        # "Main Queue" | "Night Owl Queue"
    settings: Optional[Settings] = None

    # runtime
    state: str = "queued"                 # queued|running|paused|completed|error
    total_size: int = 0
    downloaded: int = 0
    speed: float = 0.0
    error: str = ""
    file_path: str = ""
    parts: list = field(default_factory=list)
    progress: float = 0.0
    created: float = field(default_factory=time.time)

    # callbacks: on_update(task)
    on_update: Optional[Callable] = None

    # internal
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _executor: Optional[ThreadPoolExecutor] = None
    _futures: list = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _limiter: Optional[SpeedLimiter] = None
    _part_paths: list = field(default_factory=list, repr=False)
    _state_path: str = ""
    _start_mono: float = 0.0
    _last_update_mono: float = 0.0
    _last_update_bytes: int = 0
    _yt_downloader: Optional[object] = field(default=None, repr=False)

    @property
    def state_file(self) -> str:
        return os.path.splitext(self.file_path)[0] + ".idmc.json" if self.file_path else ""

    def _settings(self) -> Settings:
        return self.settings or Settings.load()

    def _probe(self) -> dict:
        """HEAD request: size, range support, filename (with YouTube auto-detection)."""
        from ..grabber.hls import youtube_video_id, resolve_youtube
        vid = youtube_video_id(self.url)
        if vid:
            yt_res = resolve_youtube(self.url)
            if not yt_res.get("error"):
                title = yt_res.get("title") or f"youtube_{vid}"
                fname = f"{title}.mp4"
                clean_name = re.sub(r'[\\/*?:"<>|]', "_", fname)
                fs = yt_res.get("filesize", 0)
                return {"length": fs, "ranges": True, "name": clean_name, "type": "video/mp4", "is_youtube": True}

        s = self._settings()
        h = {"User-Agent": s.user_agent, **self.headers}
        if self.referer:
            h["Referer"] = self.referer
        kwargs = dict(proxies=s.proxies(self.url), auth=self.auth, headers=h, cookies=self.cookies, timeout=15)
        try:
            r = requests.head(self.url, **kwargs)
            if r.status_code in (405, 501):  # server forbids HEAD -> GET without body
                r = requests.get(self.url, stream=True, **kwargs)
        except requests.exceptions.SSLError:
            self.error = ERRORS["ssl"]
            return {}
        except requests.exceptions.ProxyError:
            self.error = "Proxy connection failed"
            return {}
        except requests.exceptions.ConnectionError:
            self.error = ERRORS["connect"]
            return {}
        except requests.exceptions.Timeout:
            self.error = ERRORS["timeout"]
            return {}

        length = int(r.headers.get("Content-Length") or 0)
        accept_ranges = (r.headers.get("Accept-Ranges") or "").lower() == "bytes" or "Content-Range" in r.headers
        ctype = r.headers.get("Content-Type", "")
        cd = r.headers.get("Content-Disposition", "")
        name = ""
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.I)
        if m:
            name = m.group(1).strip()
        if not name:
            from urllib.parse import unquote, urlparse
            name = Path(unquote(urlparse(self.url).path)).name or f"download_{int(time.time())}"
        return {"length": length, "ranges": accept_ranges, "name": name, "type": ctype}

    def _unique_path(self, folder: str, name: str) -> str:
        base, ext = os.path.splitext(name)
        p = Path(folder) / name
        i = 1
        while p.exists():
            p = Path(folder) / f"{base} ({i}){ext}"
            i += 1
        return str(p)

    def _split(self, length: int) -> list:
        n = min(self.segments, max(1, length // (256 * 1024)))  # min 256KiB per part
        n = max(1, min(n, 16))
        step = length // n
        parts = []
        start = 0
        for i in range(n):
            end = length - 1 if i == n - 1 else start + step - 1
            parts.append(PartState(index=i, start=start, end=end))
            start = end + 1
        return parts

    def _load_state(self) -> None:
        sp = self.state_file
        if sp and os.path.exists(sp):
            import json
            try:
                data = json.loads(Path(sp).read_text(encoding="utf-8"))
                self.total_size = int(data.get("total", 0))
                self.parts = [PartState(**p) for p in data.get("parts", [])]
                for p in self.parts:
                    p.downloaded = min(p.downloaded, p.end - p.start + 1)
                self._part_paths = data.get("paths", [])
            except Exception:
                pass

    def _save_state(self) -> None:
        if not self.state_file:
            return
        import json
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "url": self.url, "total": self.total_size, "dest": self.file_path,
            "paths": self._part_paths,
            "parts": [{"index": p.index, "start": p.start, "end": p.end,
                       "downloaded": p.downloaded, "done": p.done} for p in self.parts],
        }
        Path(self.state_file).write_text(json.dumps(data), encoding="utf-8")

    def _worker(self, part: PartState) -> None:
        s = self._settings()
        h = {"User-Agent": s.user_agent, **self.headers}
        if self.referer:
            h["Referer"] = self.referer
        rng_start = part.start + part.downloaded
        if part.end >= 0 and rng_start > part.end:
            part.done = True
            return
        if part.end >= 0:
            h["Range"] = f"bytes={rng_start}-{part.end}"
        elif rng_start > 0:
            h["Range"] = f"bytes={rng_start}-"
        path = self._part_paths[part.index]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs = dict(proxies=s.proxies(self.url), auth=self.auth, headers=h,
                      cookies=self.cookies, stream=True, timeout=20)
        attempts = 0
        while attempts <= s.retries and not self._stop.is_set():
            try:
                with requests.get(self.url, **kwargs) as r:
                    if r.status_code not in (200, 206):
                        if r.status_code in (401, 407):
                            self.error = ERRORS["auth"]
                        elif r.status_code == 403:
                            self.error = "HTTP 403 Forbidden: Access denied by host"
                        elif r.status_code == 404:
                            self.error = "HTTP 404 Not Found: File does not exist"
                        else:
                            self.error = ERRORS["http"].format(code=r.status_code)
                        return
                    # Some servers ignore Range and reply 200 -> first part only
                    if r.status_code == 200 and part.index != 0 and self.total_size > 0:
                        self.error = ERRORS["no_range"]
                        return
                    part.status = "streaming"
                    part.last_tick = time.monotonic()
                    part.last_bytes = part.downloaded
                    with open(path, "ab" if part.downloaded else "wb") as f:
                        if part.downloaded:
                            f.seek(0, os.SEEK_END)
                        for chunk in r.iter_content(CHUNK):
                            if self._limiter:
                                self._limiter.acquire(len(chunk))
                            # Pause must be honored *after* the limiter wait too:
                            # only the chunk already being acquired may still land.
                            if self._stop.is_set():
                                part.status = "pending"
                                part.speed = 0.0
                                return
                            f.write(chunk)
                            part.downloaded += len(chunk)
                            now = time.monotonic()
                            dt = now - part.last_tick
                            if dt >= 0.5:
                                part.speed = (part.downloaded - part.last_bytes) / max(dt, 1e-6)
                                part.last_bytes = part.downloaded
                                part.last_tick = now
                            with self._lock:
                                self.downloaded += len(chunk)
                            self._tick()
                part.done = True
                part.status = "done"
                part.speed = 0.0
                return
            except requests.exceptions.SSLError:
                self.error = ERRORS["ssl"]
                return
            except requests.exceptions.Timeout:
                attempts += 1
                if attempts > s.retries:
                    self.error = ERRORS["timeout"]
                    return
            except (requests.exceptions.ConnectionError, OSError):
                attempts += 1
                if attempts > s.retries:
                    self.error = ERRORS["connect"]
                    return
            except Exception as e:  # pragma: no cover
                attempts += 1
                if attempts > s.retries:
                    self.error = f"{ERRORS['unknown']}: {e}"
                    return
            time.sleep(min(2 ** attempts, 30))

    def _tick(self) -> None:
        now = time.monotonic()
        if self._last_update_mono > 0 and (now - self._last_update_mono) < 0.25:
            return
        with self._lock:
            dt = now - self._last_update_mono if self._last_update_mono > 0 else 0.5
            if dt > 0:
                db = self.downloaded - self._last_update_bytes
                self.speed = max(0.0, db / dt)
            self._last_update_mono = now
            self._last_update_bytes = self.downloaded
            self.progress = (self.downloaded / self.total_size * 100) if self.total_size else 0.0
        if self.on_update:
            self.on_update(self)

    def _disk_ok(self) -> bool:
        folder = self.dest_dir or self._settings().save_path
        need_mb = (self.total_size / (1024 * 1024)) if self.total_size > 0 else 50
        for f in (folder, self.temp_dir()):
            try:
                Path(f).mkdir(parents=True, exist_ok=True)
                if os.path.isdir(f):
                    free_mb = shutil.disk_usage(f).free / (1024 * 1024)
                    if free_mb >= need_mb:
                        return True
            except OSError:
                continue
        self.error = ERRORS["disk"].format(need=int(need_mb), have=0)
        return False

    def _merge(self) -> None:
        dest_parent = Path(self.file_path).parent
        dest_parent.mkdir(parents=True, exist_ok=True)
        # Verify all part files exist before attempting merge
        missing = [p for p in self._part_paths if not os.path.exists(p)]
        if missing:
            # If parts are missing and an error was already captured, keep that error;
            # otherwise report incomplete download instead of misleading disk write error.
            if not self.error:
                self.error = f"Cannot assemble download (missing {len(missing)} segments)"
            return

        try:
            with open(self.file_path, "wb") as out:
                for p in self._part_paths:
                    with open(p, "rb") as f:
                        while True:
                            chunk = f.read(CHUNK)
                            if not chunk:
                                break
                            out.write(chunk)
            for p in self._part_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.remove(self.state_file)
            except OSError:
                pass
        except OSError as e:
            self.error = f"Cannot write to disk: {e}"

    def start(self) -> None:
        self._stop.clear()
        self.state = "running"
        self._start_mono = time.time()
        self._last_update_mono = time.monotonic()
        self._last_update_bytes = self.downloaded
        if self.on_update:
            self.on_update(self)
        threading.Thread(target=self._start_pipeline, daemon=True, name="idm-start-pipeline").start()

    def _start_pipeline(self) -> None:
        s = self._settings()

        from ..grabber.hls import youtube_video_id, YoutubeDownloader
        if youtube_video_id(self.url):
            self.category = "Video"
            if not self.filename:
                probe = self._probe()
                if probe.get("name"):
                    self.filename = probe["name"]
                    self.total_size = probe.get("length", 0)
            self.dest_dir = self.dest_dir or s.save_path
            self._yt_downloader = YoutubeDownloader(self, on_update=self.on_update)
            self._yt_downloader.run()
            return

        # Check if already initialized / resuming an existing download with known parts
        has_state = self._load_state_parts() or (bool(self.parts) and self.total_size > 0 and bool(self.file_path))

        if not has_state:
            probe = self._probe()
            if self.error:
                self.state = "error"
                if self.on_update:
                    self.on_update(self)
                return
            if not self.filename:
                self.filename = probe.get("name", "")
            self.category = self._settings().category_for(self.filename).get("name", self.category)
            self.total_size = probe.get("length") or self.total_size
            self.dest_dir = self.dest_dir or s.save_path
            self.file_path = self.file_path or self._unique_path(self.dest_dir, self.filename)

            if not self._load_state_parts():
                if probe.get("length", 0) == 0:
                    self.parts = [PartState(index=0, start=0, end=-1)]
                elif probe.get("ranges"):
                    self.parts = self._split(probe["length"])
                else:
                    self.parts = [PartState(index=0, start=0, end=probe["length"] - 1)]

        if self._stop.is_set():
            return

        if not self._disk_ok():
            self.state = "error"
            if self.on_update:
                self.on_update(self)
            return

        os.makedirs(self.temp_dir(), exist_ok=True)
        self._part_paths = [str(Path(self.temp_dir()) / f"{Path(self.file_path).name}.part.{p.index}") for p in self.parts]
        self._save_state()

        # restore downloaded bytes from parts for resume accounting
        with self._lock:
            self.downloaded = sum(p.downloaded for p in self.parts)

        if self._stop.is_set():
            return

        limit = self.speed_limit_kbps or (s.speed_limit_kbps if s.speed_limiter else 0)
        self._limiter = SpeedLimiter(limit) if limit else None
        self._executor = ThreadPoolExecutor(max_workers=len(self.parts), thread_name_prefix="idm-part")
        self._futures = [self._executor.submit(self._worker, p) for p in self.parts]
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor.start()
        if self.on_update:
            self.on_update(self)

    def _load_state_parts(self) -> bool:
        self._load_state()
        if not self.parts:
            return False
        # state loaded only when a matching state file exists with a non-empty dest
        return bool(self.file_path and os.path.exists(self.state_file))

    def temp_dir(self) -> str:
        return self._settings().temp_path

    def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            done = all(f.done() or self._stop.is_set() for f in self._futures) if self._futures else True
            if done:
                break
            time.sleep(0.4)
        with self._lock:
            if self._stop.is_set():
                self.state = "paused" if any(not p.done for p in self.parts) else "completed"
                self.speed = 0.0
                self._save_state()
            else:
                # merge FIRST, only then report completion (no race for consumers)
                self.state = "merging"
                self.speed = 0.0
                if self.on_update:
                    self.on_update(self)
                if not self.error:
                    self._merge()
                self.state = "completed" if not self.error else "error"
                self.progress = 100.0 if self.state == "completed" else self.progress
                if self.state != "completed":
                    self._save_state()
        if self._executor:
            self._executor.shutdown(wait=False)
        if self.on_update:
            self.on_update(self)

    def pause(self) -> None:
        self._stop.set()
        if self._yt_downloader:
            try:
                self._yt_downloader.cancel()
            except Exception:
                pass
        self.state = "paused"
        self.speed = 0.0
        self._save_state()
        if self.on_update:
            self.on_update(self)

    def cancel(self) -> None:
        self._stop.set()
        if self._yt_downloader:
            try:
                self._yt_downloader.cancel()
            except Exception:
                pass
        self.state = "error"
        self.speed = 0.0
        self.error = ERRORS["aborted"]
        for p in self._part_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.remove(self.state_file)
        except OSError:
            pass
        if self.on_update:
            self.on_update(self)

    def resume(self) -> None:
        self.start()

    @classmethod
    def from_url(cls, url: str, dest_dir: str = "", settings: Settings = None, **kw) -> "DownloadTask":
        s = settings or Settings.load()
        task = cls(url=url, dest_dir=dest_dir or s.save_path, settings=s, **kw)
        if task.segments <= 0:
            task.segments = s.max_connections
        if task.site:
            cred = s.site_passwords.get(task.site)
            if cred and not task.auth:
                task.auth = (cred.get("user", ""), cred.get("pass", ""))
        return task
