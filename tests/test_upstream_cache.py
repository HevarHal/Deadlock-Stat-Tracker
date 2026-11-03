import asyncio
import unittest

import httpx

from upstream import UpstreamClient


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_simultaneous_requests_share_fetch_and_expire(self):
        now = [0]
        calls = []

        async def handle(request):
            calls.append(request.url.path)
            await asyncio.sleep(0.01)
            return httpx.Response(200, json=[{"match_id": len(calls)}])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            cache = UpstreamClient(client, clock=lambda: now[0])
            url = "https://example.test/players/1/match-history"
            first, second = await asyncio.gather(cache.get(url), cache.get(url))
            self.assertEqual(len(calls), 1)
            self.assertIs(first, second)
            self.assertIs(await cache.get(url), first)
            now[0] = 60
            self.assertNotEqual((await cache.get(url)).json(), first.json())
            self.assertEqual(len(calls), 2)
            self.assertFalse(cache.pending)

    async def test_failures_are_not_cached_and_catalog_has_longer_ttl(self):
        now, calls = [0], []

        async def handle(request):
            calls.append(request.url.path)
            return httpx.Response(503 if "/bad" in request.url.path else 200, json=[])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            cache = UpstreamClient(client, clock=lambda: now[0])
            for _ in range(2):
                self.assertEqual(
                    (await cache.get("https://example.test/bad")).status_code, 503
                )
            self.assertEqual(len(calls), 2)
            url = "https://example.test/assets/heroes"
            first = await cache.get(url)
            now[0] = 61
            self.assertIs(await cache.get(url), first)
            now[0] = 3600
            self.assertIsNot(await cache.get(url), first)

    async def test_entry_and_byte_limits_and_malformed_json(self):
        async def handle(request):
            if request.url.path == "/invalid":
                return httpx.Response(200, text="invalid")
            return httpx.Response(200, json=[request.url.path])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            cache = UpstreamClient(client, max_entries=1, max_bytes=20)
            await cache.get("https://example.test/one")
            await cache.get("https://example.test/two")
            self.assertEqual(len(cache.cache), 1)
            self.assertLessEqual(cache.cache_bytes, 20)
            await cache.get("https://example.test/too-large-to-cache")
            self.assertEqual(len(cache.cache), 1)
            with self.assertRaises(ValueError):
                await cache.get("https://example.test/invalid")
            self.assertFalse(cache.pending)

    async def test_cancelled_waiter_does_not_cancel_shared_fetch(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def handle(request):
            started.set()
            await release.wait()
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            cache = UpstreamClient(client)
            first = asyncio.create_task(cache.get("https://example.test/history"))
            await started.wait()
            second = asyncio.create_task(cache.get("https://example.test/history"))
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            release.set()
            self.assertEqual((await second).json(), [])
            self.assertFalse(cache.pending)
