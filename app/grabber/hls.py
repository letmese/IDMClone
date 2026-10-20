"""Video grabbers — HLS (.m3u8) and YouTube stream extraction (IDM Pro core)."""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import requests


class HlsGrabber:
    """Download an HLS stream (.m3u8): pick best variant, fetch segments, join."""

    def __init__(self, url: str, dest_dir: str, settings=None, on_update=None):
        self.url = url
        self.dest_dir = dest_dir
        self.settings = settings
        self.on_update = on_update
        self.state = "queued"
        self.error = ""
        self.file_path = ""
        self.progress = 0.0
        self.total = 0
        self.downloaded = 0
        self._stop = threading.Event()

    def _get(self, url: str) -> str:
        h = {"User-Agent": (self.settings.user_agent if self.settings else
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0")}
        r = requests.get(url, headers=h, proxies=(self.settings.proxies(url) if self.settings else {}), timeout=20)
        r.raise_for_status()
        return r.text

    def _resolve_variant(self, text: str) -> str:
        best = None
        best_bw = -1
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                m = re.search(r"BANDWIDTH=(\d+)", line)
                bw = int(m.group(1)) if m else 0
                if bw > best_bw:
                    best_bw = bw
                    uri = lines[i + 1] if i + 1 < len(lines) else ""
                    best = urljoin(self.url, uri)
        return best or self.url

    def run(self):
        self.state = "running"
        try:
            text = self._get(self.url)
            if "#EXT-X-STREAM-INF" in text:
                self.url = self._resolve_variant(text)
                text = self._get(self.url)
            segs = [urljoin(self.url, ln) for ln in text.splitlines()
                    if ln and not ln.startswith("#") and not ln.startswith("<")]
            if not segs:
                self.error = "No HLS segments found"
                self.state = "error"
                return
            # figure name
            m = re.search(r"/([^/?#]+)\.m3u8", self.url)
            name = (m.group(1) if m else "stream") + ".ts"
            out = Path(self.dest_dir) / name
            i = 1
            while out.exists():
                out = Path(self.dest_dir) / f"{out.stem} ({i}){out.suffix}"
                i += 1
            self.file_path = str(out)
            temp = Path(self.file_path + ".parts")
            temp.mkdir(parents=True, exist_ok=True)
            self.total = len(segs)

            def fetch(idx_url):
                idx, u = idx_url
                if self._stop.is_set():
                    return
                r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
                                 proxies=(self.settings.proxies(u) if self.settings else {}))
                r.raise_for_status()
                (temp / f"{idx:06d}.ts").write_bytes(r.content)

            with ThreadPoolExecutor(max_workers=8) as ex:
                for f in ex.map(fetch, list(enumerate(segs))):
                    self.downloaded += 1
                    self.progress = self.downloaded / self.total * 100
                    if self.on_update:
                        self.on_update(self)

            if self._stop.is_set():
                self.state = "paused"
                return
            with open(self.file_path, "wb") as out_f:
                for idx in range(len(segs)):
                    out_f.write((temp / f"{idx:06d}.ts").read_bytes())
            shutil.rmtree(temp, ignore_errors=True)
            self.state = "completed"
            self.progress = 100.0
        except Exception as e:
            self.error = str(e)
            self.state = "error"
        if self.on_update:
            self.on_update(self)

    def cancel(self):
        self._stop.set()


def youtube_video_id(url: str) -> str:
    m = re.search(r"(?:v=|/watch\?|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def resolve_youtube(url: str, on_update=None) -> dict:
    """Return video metadata and direct stream URL(s) via yt-dlp."""
    vid = youtube_video_id(url)
    if not vid:
        return {"error": "Cannot extract video ID from URL"}
    try:
        import yt_dlp
    except ImportError:
        return {"error": "yt-dlp not installed"}

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats") or []
            streams = [{
                "url": f.get("url"), "ext": f.get("ext"), "height": f.get("height"),
                "fps": f.get("fps"), "abr": f.get("abr"), "filesize": f.get("filesize") or f.get("filesize_approx"),
                "format_id": f.get("format_id"), "note": f.get("format_note", ""),
            } for f in formats if f.get("url")]
            total_size = info.get("filesize") or info.get("filesize_approx") or 0
            return {
                "title": info.get("title", f"youtube_{vid}"),
                "id": vid,
                "duration": info.get("duration"),
                "filesize": total_size,
                "streams": streams,
            }
    except Exception as e:
        return {"error": str(e)}


class YoutubeDownloader:
    """Downloads YouTube video/audio using embedded yt-dlp and integrates into IDM task telemetry."""

    def __init__(self, task, on_update=None):
        self.task = task
        self.on_update = on_update
        self._stop = threading.Event()

    def run(self):
        import yt_dlp
        task = self.task
        task.state = "running"
        dest_dir = task.dest_dir or str(Path.home() / "Downloads")
        Path(dest_dir).mkdir(parents=True, exist_ok=True)

        # Output template
        outtmpl = os.path.join(dest_dir, "%(title)s.%(ext)s")

        def hook(d):
            if self._stop.is_set():
                raise Exception("Download aborted by user")
            status = d.get("status")
            if status == "downloading":
                dl = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or task.total_size or 0
                sp = d.get("speed") or 0.0
                task.downloaded = dl
                if total > 0:
                    task.total_size = total
                    task.progress = min(99.0, (dl / total * 100))
                task.speed = sp
                if self.on_update:
                    self.on_update(task)
            elif status == "finished":
                task.speed = 0.0
                filename = d.get("filename")
                if filename:
                    task.file_path = filename
                    task.filename = os.path.basename(filename)

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(task.url, download=True)
                if not task.filename:
                    task.filename = f"{info.get('title', 'video')}.mp4"
                if not task.file_path:
                    task.file_path = os.path.join(dest_dir, task.filename)
                task.state = "completed"
                task.progress = 100.0
                task.speed = 0.0
                task.downloaded = task.total_size
        except Exception as e:
            if self._stop.is_set():
                task.state = "paused"
                task.speed = 0.0
            else:
                task.state = "error"
                task.error = f"YouTube error: {e}"
        finally:
            if self.on_update:
                self.on_update(task)

    def cancel(self):
        self._stop.set()

