import unittest

from metrics import calculate_metrics, most_played_hero


class MetricsTests(unittest.TestCase):
    def test_outcomes_cutoff_missing_souls_and_zero_deaths(self):
        matches = [
            {
                "hero_id": 2,
                "start_time": 99,
                "player_match_outcome": 0,
                "player_kills": 3,
                "net_worth": 100,
            },
            {
                "hero_id": 1,
                "start_time": 100,
                "player_match_outcome": 5,
                "player_kills": 2,
            },
            {
                "hero_id": 1,
                "start_time": 101,
                "player_match_outcome": 1,
                "net_worth": 300,
            },
            {
                "hero_id": None,
                "start_time": 102,
                "player_match_outcome": 2,
                "net_worth": None,
            },
        ]
        self.assertEqual(
            calculate_metrics(matches, 100),
            {
                "total_matches": 4,
                "wins": 1,
                "losses": 1,
                "unscored": 1,
                "kill_death_ratio": 5.0,
                "avg_souls": 200,
            },
        )
        self.assertEqual(most_played_hero(matches), ("1", 2))
        self.assertEqual(most_played_hero([]), ("Unknown", 0))

    def test_ties_use_first_seen_hero(self):
        self.assertEqual(most_played_hero([{"hero_id": 2}, {"hero_id": 1}]), ("2", 1))
