"""On-demand item timelines and starting guides for a match participant."""

import httpx
from fastapi import APIRouter, HTTPException, Path

router = APIRouter()
API_BASE = "https://api.deadlock-api.com/v1"


def item_view(item_id, catalog):
    asset = catalog.get(item_id, {})
    return {
        "id": item_id,
        "name": asset.get("name", f"Item {item_id}"),
        "image": (
            asset.get("shop_image_webp")
            or asset.get("shop_image")
            or asset.get("image_webp")
            or asset.get("image")
        ),
    }


def purchase_timeline(player, catalog):
    """Filter shop purchases and distinguish sales from consumed upgrade components."""
    # Metadata also contains ability unlocks/upgrades; these are not shop purchases.
    purchases = [
        {
            **item_view(item["item_id"], catalog),
            "time": item.get("game_time_s", 0),
            # Bit 0 marks a component consumed by an upgrade, rather than a sale.
            "soldTime": None
            if (item.get("flags") or 0) & 1
            else item.get("sold_time_s") or None,
        }
        for item in player.get("items", [])
        if catalog.get(item.get("item_id"), {}).get("type") == "upgrade"
        and catalog[item["item_id"]].get("shopable", False)
    ]
    purchases.sort(key=lambda item: item["time"])
    return purchases


async def fetch_starting_guide(client, player, build_id, catalog):
    """A missing or unavailable guide must not hide the item timeline."""
    guide = None
    guide_message = "The starting build guide was not recorded for this match."
    if build_id:
        try:
            response = await client.get(
                f"{API_BASE}/builds/{player['hero_id']}/{build_id}"
            )
            if response.status_code == 200:
                build = response.json()["hero_build"]
                guide = {
                    "id": build_id,
                    "name": build["name"],
                    "description": build.get("description"),
                    "version": build.get("version"),
                    "authorAccountId": build.get("author_account_id"),
                    "groups": [
                        {
                            "name": group["name"],
                            "description": group.get("description"),
                            "items": [
                                {
                                    **item_view(mod["ability_id"], catalog),
                                    "annotation": mod.get("annotation"),
                                }
                                for mod in group.get("mods") or []
                            ],
                        }
                        for group in build.get("details", {}).get("mod_categories", [])
                    ],
                }
            else:
                guide_message = "The recorded starting guide could not be retrieved. It may no longer be public or available."
        except (httpx.RequestError, KeyError, ValueError):
            guide_message = "The starting guide is temporarily unavailable."
    return guide, guide_message


@router.get("/api/player/{account_id}/matches/{match_id}/build")
async def match_build(account_id: int = Path(ge=0), match_id: int = Path(ge=0)):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            metadata = await client.get(
                f"{API_BASE}/matches/{match_id}/metadata",
                params={"disable_steam": "true"},
            )
            if metadata.status_code == 404:
                raise HTTPException(
                    404, "Detailed data is not available for this match."
                )
            if metadata.status_code != 200:
                raise HTTPException(
                    502, "Match details are temporarily unavailable. Please try again."
                )
            data = metadata.json()
            player = next(
                (
                    p
                    for p in data.get("match_info", {}).get("players", [])
                    if str(p.get("account_id")) == str(account_id)
                ),
                None,
            )
            if player is None:
                raise HTTPException(
                    404, "This player was not found in the match metadata."
                )
            assets = await client.get(f"{API_BASE}/assets/items")
            if assets.status_code != 200:
                raise HTTPException(
                    502, "Item details are temporarily unavailable. Please try again."
                )
            catalog = {item["id"]: item for item in assets.json()}
            purchases = purchase_timeline(player, catalog)
            build_id = player.get("hero_build_id") or data.get(
                "hero_build_ids", {}
            ).get(str(account_id))
            guide, guide_message = await fetch_starting_guide(
                client, player, build_id, catalog
            )
            return {
                "matchId": match_id,
                "accountId": str(account_id),
                "items": purchases,
                "guide": guide,
                "guideMessage": guide_message if guide is None else None,
            }
    except httpx.RequestError:
        raise HTTPException(
            502, "Match details could not be reached. Please try again."
        )
