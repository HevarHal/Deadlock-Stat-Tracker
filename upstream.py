"""Worker-local HTTP connection pool and bounded, successful-response cache."""

import asyncio
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

API_BASE = "https://api.deadlock-api.com/v1"
REQUEST_TIMEOUT_SECONDS = 20
MATCH_CACHE_SECONDS = 5 * 60
CATALOG_CACHE_SECONDS = 3600
MAX_CACHE_ENTRIES = 128
MAX_CACHE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CacheEntry:
    expires_at: float
    response: "JSONResponse"
    size_bytes: int


class JSONResponse:
    """Share parsed JSON as read-only data across requests."""

    def __init__(self, response, payload):
        self.status_code = response.status_code
        self.payload = payload
        self.fetched_at = datetime.now(UTC).replace(tzinfo=None)

    def json(self):
        return self.payload


class UpstreamClient:
    """Cache JSON and share in-flight requests within one application worker.

    Search bypasses the cache. Catalogs use the longer catalog lifetime; other
    resources use the match lifetime. Only successful, valid JSON is retained.
    Call close() during shutdown to cancel unfinished fetches.
    """

    def __init__(
        self,
        client,
        *,
        clock=time.monotonic,
        max_entries=MAX_CACHE_ENTRIES,
        max_bytes=MAX_CACHE_BYTES,
    ):
        self.client = client
        self.clock = clock
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.pending = {}

    def discard(self, key):
        """Remove an entry and update the serialized-body byte count."""
        entry = self.cache.pop(key, None)
        if entry:
            self.cache_bytes -= entry.size_bytes

    def store(self, key, response, size_bytes, ttl):
        """Remove expired entries, then evict least recently used entries if needed."""
        now = self.clock()
        expired_keys = [
            key for key, entry in self.cache.items() if entry.expires_at <= now
        ]
        for expired_key in expired_keys:
            self.discard(expired_key)

        self.cache[key] = CacheEntry(now + ttl, response, size_bytes)
        self.cache_bytes += size_bytes
        while len(self.cache) > self.max_entries or self.cache_bytes > self.max_bytes:
            oldest_key = next(iter(self.cache))
            self.discard(oldest_key)

    async def get(self, url, **kwargs):
        """Return cached data or await a fetch shared by identical URL/params."""
        # Search remains uncached; catalogs change much less often than matches.
        ttl = CATALOG_CACHE_SECONDS if "/assets/" in url else MATCH_CACHE_SECONDS
        if "/steam-search" in url:
            return await self.client.get(url, **kwargs)
        key = (url, tuple(sorted((kwargs.get("params") or {}).items())))
        entry = self.cache.get(key)
        if entry and entry.expires_at > self.clock():
            self.cache.move_to_end(key)
            return entry.response
        self.discard(key)
        if key not in self.pending:
            self.pending[key] = asyncio.create_task(self.fetch(key, url, ttl, kwargs))
        # A disconnected browser must not cancel work shared by another request.
        return await asyncio.shield(self.pending[key])

    async def fetch(self, key, url, ttl, kwargs):
        """Fetch once; always clear the in-flight entry, including on failure."""
        try:
            response = await self.client.get(url, **kwargs)
            size = len(response.content)
            if response.status_code == 200 and size <= self.max_bytes:
                # Do not retain malformed upstream JSON as a successful response.
                response = JSONResponse(response, response.json())
                self.store(key, response, size, ttl)
            return response
        finally:
            self.pending.pop(key, None)

    async def close(self):
        """Cancel and await outstanding upstream requests before shutdown."""
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@asynccontextmanager
async def client_for(request):
    pooled = getattr(request.app.state, "upstream", None)
    if pooled is not None:
        yield pooled
    else:
        # Also supports standalone routers and tests without application lifespan.
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            yield client


async def fetch_hero_names(client):
    """Hero names are optional; an unavailable catalog should not hide player data."""
    try:
        response = await client.get(f"{API_BASE}/assets/heroes")
        if response.status_code == 200:
            return {str(hero["id"]): hero["name"] for hero in response.json()}
    except httpx.RequestError:
        pass
    return {}
