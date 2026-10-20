import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import database

database.init_db = lambda: None

import main
from fastapi.testclient import TestClient


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


class SummaryStatusTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[main.get_db] = lambda: FakeDatabase()
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_standard_only_player_returns_success_without_ranked_matches(self):
        standard_match = {"match_mode": 1, "hero_id": 1}
        fake_client = FakeAsyncClient(FakeResponse(200, [standard_match]))

        with patch("main.httpx.AsyncClient", return_value=fake_client):
            response = self.client.get("/api/player/123/summary?scope=all")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["hasRankedMatches"])
        self.assertEqual(body["metrics"]["totalMatches"], 0)
        self.assertIsNone(body["metrics"]["winRatePercentage"])

    def test_missing_upstream_profile_still_returns_404(self):
        fake_client = FakeAsyncClient(FakeResponse(404, {"detail": "not found"}))

        with patch("main.httpx.AsyncClient", return_value=fake_client):
            response = self.client.get("/api/player/123/summary?scope=all")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()