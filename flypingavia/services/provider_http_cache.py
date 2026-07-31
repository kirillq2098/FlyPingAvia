"""In-memory TTL cache for Travelpayouts Data API JSON responses."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes


@dataclass
class _Entry:
    payload: dict
    expires_at: float


class ProviderHttpCache:
    """Process-local cache. Keys never include raw secrets in logs."""

    def __init__(self, *, ttl_seconds: float = DEFAULT_TTL_SECONDS, max_entries: int = 512) -> None:
        self._ttl = float(ttl_seconds)
        self._max = max(32, int(max_entries))
        self._store: dict[str, _Entry] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(url: str, params: dict[str, str]) -> str:
        safe = {str(k): str(v) for k, v in params.items() if str(k).lower() != "token"}
        blob = json.dumps({"url": url, "params": safe}, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        now = time.monotonic()
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if entry.expires_at < now:
            self._store.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return entry.payload

    def set(self, key: str, payload: dict) -> None:
        if len(self._store) >= self._max:
            # Drop oldest ~10%
            doomed = sorted(self._store.items(), key=lambda kv: kv[1].expires_at)[
                : max(1, self._max // 10)
            ]
            for k, _ in doomed:
                self._store.pop(k, None)
        self._store[key] = _Entry(payload=payload, expires_at=time.monotonic() + self._ttl)

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0


# Shared default for Data API providers in this process.
default_provider_http_cache = ProviderHttpCache()
