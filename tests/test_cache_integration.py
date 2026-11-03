import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from test_summary_status import main


class IntegrationTests(unittest.TestCase):
    def test_profile_routes_share_upstream_history_during_lifespan(self):
        calls = []

        async def handle(request):
            calls.append(request.url.path)
            if request.url.path.endswith("/match-history"):
                payload = [
                    {
                        "match_id": 1,
                        "match_mode": 1,
                        "hero_id": 1,
                        "start_time": 1,
                        "player_match_outcome": 1,
                        "player_kills": 4,
                        "player_deaths": 2,
                        "net_worth": 100,
                    }
                ]
            else:
                payload = [{"id": 1, "name": "Hero One"}]
            return httpx.Response(200, json=payload)

        original = httpx.AsyncClient

        def client(**kwargs):
            return original(transport=httpx.MockTransport(handle), **kwargs)

        with (
            patch("main.httpx.AsyncClient", side_effect=client),
            patch("main.init_db"),
            TestClient(main.app) as browser,
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(
                    pool.map(
                        browser.get,
                        [
                            "/api/player/123/summary?scope=all",
                            "/api/player/123/matches?scope=all",
                        ],
                    )
                )
            self.assertTrue(all(r.status_code == 200 for r in responses))
            self.assertEqual(responses[0].json()["metrics"]["dominantHero"], "Hero One")
            self.assertEqual(responses[1].json()["matches"][0]["heroName"], "Hero One")
            browser.get("/api/player/123/matches?scope=all&page=2")
            self.assertEqual(calls.count("/v1/players/123/match-history"), 1)
            self.assertEqual(calls.count("/v1/assets/heroes"), 1)
        self.assertFalse(hasattr(main.app.state, "upstream"))

    def test_summary_cache_requires_current_version_and_fresh_timestamp(self):
        db = MagicMock()
        record = SimpleNamespace(**{field: 1 for field in main.SUMMARY_FIELDS.values()})
        record.season = main.SEASON_1_CACHE_VERSION
        record.updated_at = main.utc_now()
        db.query.return_value.filter.return_value.first.return_value = record
        self.assertIsNotNone(main.read_cached_summary(db, "123"))
        db.commit.assert_not_called()
        db.rollback.assert_called_once()
        record.updated_at = main.utc_now() - timedelta(seconds=61)
        self.assertIsNone(main.read_cached_summary(db, "123"))
        record.updated_at = main.utc_now()
        record.season = "old_version"
        self.assertIsNone(main.read_cached_summary(db, "123"))

    def test_persisting_summary_does_not_extend_cached_history_age(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        fetched_at = main.utc_now() - timedelta(seconds=50)
        main.save_summary(db, "123", {"wins": 1}, fetched_at)
        saved = db.add.call_args.args[0]
        self.assertEqual(saved.updated_at, fetched_at)
        db.commit.assert_called_once()
