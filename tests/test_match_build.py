import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import match_details


class MatchBuildTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(match_details.router)
        self.client = TestClient(app)
        self.metadata = {
            "match_info": {
                "players": [
                    {
                        "account_id": 123,
                        "hero_id": 77,
                        "items": [
                            {"item_id": 10, "game_time_s": 80, "sold_time_s": 150},
                            {"item_id": 20, "game_time_s": 10},
                            {"item_id": 10, "game_time_s": 20},
                        ],
                    },
                    {"account_id": 456, "hero_id": 77, "items": []},
                ]
            },
            "hero_build_ids": {"123": 999},
        }
        self.assets = [
            {"id": 10, "name": "Extra Spirit", "type": "upgrade", "shopable": True},
            {"id": 20, "name": "Ability", "type": "ability"},
        ]
        self.guide = {
            "hero_build": {
                "name": "Example guide",
                "version": 3,
                "details": {
                    "mod_categories": [
                        {
                            "name": "Early game",
                            "mods": [{"ability_id": 10, "annotation": "Buy first"}],
                        }
                    ]
                },
            }
        }

    def request(
        self, metadata_status=200, guide_status=200, asset_status=200, account=123
    ):
        async def handle(request):
            if request.url.path.endswith("/metadata"):
                self.assertEqual(request.url.params.get("disable_steam"), "true")
                return httpx.Response(metadata_status, json=self.metadata)
            if request.url.path.endswith("/assets/items"):
                return httpx.Response(asset_status, json=self.assets)
            self.assertEqual(request.url.path, "/v1/builds/77/999")
            return httpx.Response(guide_status, json=self.guide)

        original = httpx.AsyncClient

        def client(**kwargs):
            return original(transport=httpx.MockTransport(handle), **kwargs)

        with patch("match_details.httpx.AsyncClient", side_effect=client):
            return self.client.get(f"/api/player/{account}/matches/100/build")

    def test_timeline_filters_abilities_orders_purchases_and_preserves_sales(self):
        result = self.request().json()
        self.assertEqual([item["time"] for item in result["items"]], [20, 80])
        self.assertEqual(result["items"][1]["soldTime"], 150)
        self.assertEqual(result["guide"]["id"], 999)
        self.assertEqual(
            result["guide"]["groups"][0]["items"][0]["annotation"], "Buy first"
        )

    def test_unavailable_guide_does_not_hide_purchases(self):
        result = self.request(guide_status=404).json()
        self.assertEqual(len(result["items"]), 2)
        self.assertIsNone(result["guide"])
        self.assertIn("could not be retrieved", result["guideMessage"])

    def test_upgrade_components_are_not_reported_as_sales(self):
        self.metadata["match_info"]["players"][0]["items"][0]["flags"] = 1
        result = self.request().json()
        self.assertEqual(len(result["items"]), 2)
        self.assertIsNone(result["items"][1]["soldTime"])
        # Other flags do not suppress an actual sale.
        self.metadata["match_info"]["players"][0]["items"][0]["flags"] = 2
        self.assertEqual(self.request().json()["items"][1]["soldTime"], 150)

    def test_unrecorded_guide_and_empty_inventory(self):
        result = self.request(account=456).json()
        self.assertEqual(result["items"], [])
        self.assertIsNone(result["guide"])
        self.assertIn("not recorded", result["guideMessage"])

    def test_missing_match_and_missing_participant(self):
        self.assertEqual(self.request(metadata_status=404).status_code, 404)
        self.assertEqual(self.request(account=789).status_code, 404)

    def test_upstream_failures_and_invalid_ids(self):
        self.assertEqual(self.request(metadata_status=429).status_code, 502)
        self.assertEqual(self.request(asset_status=503).status_code, 502)
        self.assertEqual(
            self.client.get("/api/player/-1/matches/100/build").status_code, 422
        )


if __name__ == "__main__":
    unittest.main()
