import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import database

database.init_db = lambda: None

from fastapi.testclient import TestClient

import main


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, match_history_response):
        self.match_history_response = match_history_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url):
        if url.endswith("/match-history"):
            return self.match_history_response
        return FakeResponse(200, [])


class FakeQuery:
    def filter(self, *_args):
        return self

    def first(self):
        return None


class FakeDatabase:
    def query(self, *_args):
        return FakeQuery()

    def rollback(self):
        pass

    def commit(self):
        pass


class SummaryStatusTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[main.get_db] = lambda: FakeDatabase()
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_all_scope_includes_standard_matches(self):
        standard_match = {
            "match_mode": 1,
            "hero_id": 1,
            "start_time": 1,
            "player_match_outcome": 1,
            "player_kills": 5,
            "player_deaths": 2,
            "net_worth": 1000,
        }
        fake_client = FakeAsyncClient(FakeResponse(200, [standard_match]))

        with patch("main.httpx.AsyncClient", return_value=fake_client):
            response = self.client.get("/api/player/123/summary?scope=all")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["hasRankedMatches"])
        self.assertEqual(body["metrics"]["totalMatches"], 1)
        self.assertEqual(body["metrics"]["winRatePercentage"], 100.0)

    def test_season_scope_excludes_standard_matches(self):
        standard = {"match_mode": 1, "hero_id": 1, "start_time": main.SEASON_1_START}
        with patch(
            "main.httpx.AsyncClient",
            return_value=FakeAsyncClient(FakeResponse(200, [standard])),
        ):
            response = self.client.get("/api/player/123/summary?scope=season1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["totalMatches"], 0)

    def test_all_scope_counts_unknown_outcomes_without_lowering_win_rate(self):
        base = {
            "hero_id": 1,
            "start_time": 1,
            "player_kills": 5,
            "player_deaths": 2,
            "net_worth": 1000,
        }
        matches = [
            dict(base, match_mode=4, player_match_outcome=1),
            dict(base, match_mode=1, player_match_outcome=2),
            dict(base, match_mode=3, player_match_outcome=0),
        ]
        with patch(
            "main.httpx.AsyncClient",
            return_value=FakeAsyncClient(FakeResponse(200, matches)),
        ):
            response = self.client.get("/api/player/123/summary?scope=all")
        self.assertEqual(response.status_code, 200)
        metrics = response.json()["metrics"]
        self.assertEqual(metrics["totalMatches"], 3)
        self.assertEqual(metrics["wins"], 1)
        self.assertEqual(metrics["losses"], 1)
        self.assertEqual(metrics["winRatePercentage"], 50.0)

    def test_missing_upstream_profile_still_returns_404(self):
        fake_client = FakeAsyncClient(FakeResponse(404, {"detail": "not found"}))

        with patch("main.httpx.AsyncClient", return_value=fake_client):
            response = self.client.get("/api/player/123/summary?scope=all")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
