"""Settings storage — mirrors IDMan.exe option keys (registry-backed in the original).

Option keys seen in the decompiled dump:
HttpProxy, HttpsProxy, FtpProxy, UseHttpProxy, UseHttpsProxy, UseFtpProxy,
ProxyEnable, nProxyMode, Socks5ProxyDNS, ExceptionProxyServers, uBrProxy/ou_uBrProxy,
isUseWinDialUp, DialUpEntry, MaxConnectionsNumber, bUseSpeedLimiter, psnSpeedLimit,
bSaveLogs, sls_maxSpeed, TempPath, LocalFileName, mAttempts, DarkMode_Explorer
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("APPDATA", Path.home())) / "IDMClone" / "config.json"
DEFAULT_DOWNLOADS = str(Path.home() / "Downloads")
DEFAULT_TEMP = str(Path(os.environ.get("TEMP", "C:/Windows/Temp")) / "IDMClone")


@dataclass
class Settings:
    max_connections: int = 8            # MaxConnectionsNumber
    max_concurrent_tasks: int = 3
    retries: int = 5                    # mAttempts
    speed_limiter: bool = False         # bUseSpeedLimiter
    speed_limit_kbps: int = 0           # psnSpeedLimit (0 = unlimited)
    save_path: str = DEFAULT_DOWNLOADS  # default "Downloads"
    temp_path: str = DEFAULT_TEMP       # TempPath
    log_save: bool = True               # bSaveLogs
    log_path: str = str(Path(DEFAULT_DOWNLOADS) / "IDMClone.log")

    # Proxy block
    use_proxy: bool = False             # ProxyEnable
    http_proxy: str = ""                # HttpProxy
    https_proxy: str = ""               # HttpsProxy
    ftp_proxy: str = ""                 # FtpProxy
    use_http_proxy: bool = True
    use_https_proxy: bool = True
    use_ftp_proxy: bool = True
    socks5_dns: bool = True             # Socks5ProxyDNS (remote DNS)
    proxy_mode: int = 0                 # nProxyMode: 0 manual, 1 from browser, 2 none
    proxy_user: str = ""
    proxy_pass: str = ""
    proxy_exceptions: list = field(default_factory=list)  # ExceptionProxyServers

    # Dial-up
    use_dialup: bool = False            # isUseWinDialUp
    dialup_entry: str = ""              # DialUpEntry

    # Categories
    categories: list = field(default_factory=lambda: [
        {"name": "Video", "path": str(Path.home() / "Downloads" / "Video")},
        {"name": "Music", "path": str(Path.home() / "Downloads" / "Music")},
        {"name": "Documents", "path": str(Path.home() / "Downloads" / "Documents")},
        {"name": "Programs", "path": str(Path.home() / "Downloads" / "Programs")},
        {"name": "Compressed", "path": str(Path.home() / "Downloads" / "Compressed")},
        {"name": "Games", "path": str(Path.home() / "Downloads" / "Games")},
    ])

    # Site passwords: {host: {"user": str, "pass": str, "realm": str}}
    site_passwords: dict = field(default_factory=dict)

    # Scheduler
    schedule_enabled: bool = False
    schedule_entries: list = field(default_factory=list)  # ScheduleEntry as dicts

    # Quota
    quota_enabled: bool = False
    quota_period: str = "monthly"       # monthly | weekly
    quota_bytes: int = 0

    # Themes & Appearance
    active_theme: str = "Obsidian Cyber Mica"   # Obsidian Cyber Mica | Electric Cyan Protocol | Titanium Midnight | Aurora Glow | Clean Frost (Light)
    dark_mode: bool = True              # DarkMode_Explorer
    completion_sound: bool = True
    shutdown_after_queue: bool = False
    clipboard_monitoring: bool = True
    remember_download_choices: bool = True

    # Engine tuning
    aggressive_segment_optimization: bool = True
    connection_timeout: int = 20
    default_connections: int = 16

    # Night Owl Queue
    night_owl_enabled: bool = False
    night_owl_time: str = "02:00"

    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

    def proxies(self, url: str = "") -> dict:
        """Build requests-compatible proxies dict honoring per-protocol flags + exceptions."""
        if not self.use_proxy:
            return {}
        from urllib.parse import urlparse
        if url:
            host = urlparse(url).hostname or ""
            if host in self.proxy_exceptions:
                return {}
        p = {}
        if self.http_proxy and self.use_http_proxy:
            p["http"] = self._with_auth(self.http_proxy)
        if self.https_proxy and self.use_https_proxy:
            p["https"] = self._with_auth(self.https_proxy)
        if self.ftp_proxy and self.use_ftp_proxy:
            p["ftp"] = self._with_auth(self.ftp_proxy)
        return p

    def _with_auth(self, proxy: str) -> str:
        if not (self.proxy_user and proxy.startswith("http")):
            return proxy
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(proxy)
        netloc = f"{self.proxy_user}:{self.proxy_pass}@{parts.netloc}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

    def category_for(self, filename: str) -> dict:
        ext = Path(filename).suffix.lower()
        table = {
            ".mp4": "Video", ".mkv": "Video", ".avi": "Video", ".mov": "Video", ".webm": "Video",
            ".flv": "Video", ".wmv": "Video", ".ts": "Video", ".m4v": "Video", ".3gp": "Video",
            ".mp3": "Music", ".wav": "Music", ".flac": "Music", ".aac": "Music", ".ogg": "Music",
            ".m4a": "Music", ".wma": "Music",
            ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents", ".txt": "Documents",
            ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents", ".pptx": "Documents",
            ".epub": "Documents",
            ".exe": "Programs", ".msi": "Programs", ".apk": "Programs", ".dmg": "Programs",
            ".zip": "Compressed", ".rar": "Compressed", ".7z": "Compressed", ".tar": "Compressed",
            ".gz": "Compressed", ".bz2": "Compressed", ".xz": "Compressed", ".iso": "Compressed",
            ".nrg": "Compressed",
        }
        name = table.get(ext)
        for cat in self.categories:
            if cat["name"] == name:
                return cat
        return {"name": "Other", "path": self.save_path}

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                known = {f for f in cls.__dataclass_fields__}
                data = {k: v for k, v in data.items() if k in known}
                s = cls(**data)
                # Ensure paths exist and are writable, else fall back to defaults
                try:
                    Path(s.save_path).mkdir(parents=True, exist_ok=True)
                except Exception:
                    s.save_path = DEFAULT_DOWNLOADS
                try:
                    Path(s.temp_path).mkdir(parents=True, exist_ok=True)
                except Exception:
                    s.temp_path = DEFAULT_TEMP
                return s
            except Exception:
                pass
        s = cls()
        Path(s.save_path).mkdir(parents=True, exist_ok=True)
        Path(s.temp_path).mkdir(parents=True, exist_ok=True)
        return s

