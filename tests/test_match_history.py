import unittest
from unittest.mock import patch

from test_summary_status import main, FakeAsyncClient, FakeResponse
from fastapi.testclient import TestClient


def match(match_id, mode=4, start=None, outcome=1):
    return {"match_id": match_id, "match_mode": mode,
            "start_time": main.SEASON_1_START + match_id if start is None else start,
            "hero_id": 99, "player_match_outcome": outcome,
            "player_kills": 7, "player_deaths": 3, "player_assists": 12,
            "net_worth": 23456, "match_duration_s": 1801}


class MatchHistoryTests(unittest.TestCase):
    def test_profile_rank_uses_peak_for_all_and_latest_within_season(self):
        matches = [
            {**match(1, start=main.SEASON_1_START - 1), "ranked_display_badge": 116},
            {**match(2), "ranked_display_badge": 95},
            {**match(3), "ranked_display_badge": 83},
            {**match(4, mode=1), "ranked_display_badge": 126},
            match(5),
        ]
        self.assertEqual(self.request(matches, "scope=all&page=2&page_size=1").json()["rankBadge"], 116)
        self.assertEqual(self.request(matches, "scope=season1").json()["rankBadge"], 83)
        self.assertEqual(self.request(matches, "scope=season1").json()["highestRankBadge"], 116)
        self.assertEqual(self.request(matches, "scope=all&page=2&page_size=1").json()["highestRankBadge"], 116)
        self.assertIsNone(self.request([match(1)]).json()["rankBadge"])

    def test_rank_badge_is_only_exposed_for_ranked_matches(self):
        ranked = {**match(1), "ranked_display_badge": 83}
        unranked = {**match(2, mode=1), "ranked_display_badge": 83}
        missing = match(3)
        rows = {m["matchId"]: m for m in self.request([ranked, unranked, missing]).json()["matches"]}
        self.assertEqual(rows[1]["rankedBadge"], 83)
        self.assertIsNone(rows[2]["rankedBadge"])
        self.assertIsNone(rows[3]["rankedBadge"])
        self.assertEqual(rows[1]["heroId"], 99)

    def setUp(self):
        self.client = TestClient(main.app)

    def request(self, matches, query="scope=all", status=200):
        fake = FakeAsyncClient(FakeResponse(status, matches))
        with patch("main.httpx.AsyncClient", return_value=fake):
            return self.client.get("/api/player/123/matches?" + query)

    def test_all_modes_sorted_and_paginated_without_overlap(self):
        matches = [match(i, mode=1 if i % 2 else 4) for i in range(1, 24)]
        first = self.request(matches).json()
        second = self.request(matches, "scope=all&page=2").json()
        self.assertEqual(first["totalMatches"], 23)
        self.assertEqual(first["totalPages"], 2)
        self.assertEqual([m["matchId"] for m in first["matches"]], list(range(23, 3, -1)))
        self.assertEqual([m["matchId"] for m in second["matches"]], [3, 2, 1])

    def test_season_uses_same_ranked_filter_and_exclusive_end_as_summary(self):
        matches = [match(1, start=main.SEASON_1_START), match(2, mode=1),
                   match(3, start=main.SEASON_1_START - 1), match(4, start=main.SEASON_1_END)]
        result = self.request(matches, "scope=season1").json()
        self.assertEqual(result["totalMatches"], 1)
        self.assertEqual(result["matches"][0]["matchId"], 1)

    def test_outcomes_and_match_fields_are_preserved(self):
        result = self.request([match(i, outcome=i) for i in range(6)]).json()
        rows = {m["matchId"]: m for m in result["matches"]}
        self.assertEqual([rows[i]["result"] for i in range(6)],
                         ["Unknown", "Win", "Loss", "Penalized", "Party penalty", "Unscored"])
        self.assertEqual(rows[1]["kills"], 7)
        self.assertEqual(rows[1]["assists"], 12)
        self.assertEqual(rows[1]["durationSeconds"], 1801)
        self.assertEqual(rows[1]["souls"], 23456)
        self.assertEqual(rows[1]["heroName"], "Hero 99")

    def test_empty_history_and_page_past_end(self):
        result = self.request([]).json()
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["totalPages"], 0)
        result = self.request([match(1)], "scope=all&page=2").json()
        self.assertEqual(result["totalMatches"], 1)
        self.assertEqual(result["matches"], [])

    def test_invalid_pagination_and_scope_are_rejected(self):
        for query in ["page=0", "page_size=101", "scope=invalid"]:
            self.assertEqual(self.request([], query).status_code, 422)
        self.assertEqual(self.client.get('/api/player/not-a-number/matches').status_code, 422)

    def test_upstream_error_does_not_look_like_empty_history(self):
        self.assertEqual(self.request({}, status=404).status_code, 404)
        self.assertEqual(self.request({}, status=429).status_code, 502)
