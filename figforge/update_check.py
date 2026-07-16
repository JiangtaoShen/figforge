"""Silent update check against the GitHub releases API.

A daemon thread fetches the latest release tag and emits a Qt signal
(cross-thread, queued) — nothing blocks the UI, all failures are quiet.
"""
from __future__ import annotations

import json
import threading
import urllib.request

from PySide6 import QtCore

RELEASES_API = ("https://api.github.com/repos/JiangtaoShen/figforge"
                "/releases/latest")
RELEASES_URL = "https://github.com/JiangtaoShen/figforge/releases/latest"


def parse_version(s: str) -> tuple[int, int, int]:
    """'v0.3.1' / '0.3.1-rc1' -> (0, 3, 1); malformed parts become 0."""
    s = s.strip().lstrip("vV").split("-", 1)[0]
    out: list[int] = []
    for part in s.split(".")[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)  # type: ignore[return-value]


def is_newer(remote: str, current: str) -> bool:
    return parse_version(remote) > parse_version(current)


class UpdateChecker(QtCore.QObject):
    updateAvailable = QtCore.Signal(str)     # newer tag, e.g. "v0.4.0"
    upToDate = QtCore.Signal()
    failed = QtCore.Signal(str)

    def check(self, current_version: str, timeout: float = 10.0) -> None:
        threading.Thread(target=self._worker,
                         args=(current_version, timeout), daemon=True).start()

    def _worker(self, current: str, timeout: float) -> None:
        try:
            req = urllib.request.Request(
                RELEASES_API,
                headers={"User-Agent": "FigForge",
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            tag = str(data.get("tag_name") or "")
            if tag and is_newer(tag, current):
                self.updateAvailable.emit(tag)
            else:
                self.upToDate.emit()
        except Exception as e:                       # offline etc. — quiet
            self.failed.emit(str(e))
