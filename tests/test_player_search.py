import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from test_summary_status import FakeResponse, main


class PlayerSearchTests(unittest.TestCase):
    def request(self, players, query="dadlock", status=200):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = FakeResponse(status, players)
        with patch("main.httpx.AsyncClient", return_value=client):
            response = TestClient(main.app).get(
                "/api/player/search", params={"query": query}
            )
        return response, client

    def test_exact_name_precedes_similar_and_active_players(self):
        players = [
            {"account_id": i, "personaname": name, "avatar": "avatar.png"}
            for i, name in enumerate(
                ["deadlock", "xDadlock", "DadlockFan", "DADLOCK", "dadlock"]
            )
        ]
        response, upstream = self.request(players, query=" dadlock ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [p["playerName"] for p in response.json()["players"]],
            ["DADLOCK", "dadlock", "DadlockFan", "xDadlock", "deadlock"],
        )
        params = upstream.get.call_args.kwargs["params"]
        self.assertEqual(params["search_query"], "dadlock")
        self.assertEqual(params["min_matches_played_last_30d"], 0)
        self.assertEqual(params["matches_played_weight"], 0)
        self.assertEqual(params["limit"], 100)

    def test_result_count_and_response_format_stay_compatible(self):
        players = [
            {"account_id": i, "personaname": f"Player {i}", "avatar": "avatar.png"}
            for i in range(20)
        ]
        response, _ = self.request(players)
        results = response.json()["players"]
        self.assertEqual(len(results), 10)
        self.assertEqual(
            results[0],
            {"accountId": 0, "playerName": "Player 0", "avatar": "avatar.png"},
        )

    def test_upstream_failure_is_not_reported_as_no_matches(self):
        self.assertEqual(self.request([], status=429)[0].status_code, 502)
        self.assertEqual(self.request([], status=404)[0].status_code, 404)

    def test_blank_query_does_not_call_upstream(self):
        response, upstream = self.request([], query="   ")
        self.assertEqual(response.status_code, 422)
        upstream.get.assert_not_called()
