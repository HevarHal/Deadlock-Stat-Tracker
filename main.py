import logging
import time
from typing import Annotated

import httpx
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import PlayerStat, SessionLocal, init_db
from match_details import router as match_details_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Deadlock Live Analytics Pipeline")
app.include_router(match_details_router)

# Boots up database structures inside Docker on app launch
init_db()
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SEASON_1 = "season_1_player_outcomes_v8"
SEASON_1_START = 1785430800
SEASON_1_END = 1793854800
RANKED_MATCH_MODE = 4
UNSCORED_LOOKBACK_SECONDS = 90 * 24 * 60 * 60


def select_matches(matches, scope):
    if scope == "all":
        return matches
    return [
        match
        for match in matches
        if match.get("match_mode") == RANKED_MATCH_MODE
        and SEASON_1_START <= match["start_time"] < SEASON_1_END
    ]


def valid_rank_badges(matches):
    """Return ranked badges in match order, excluding missing or malformed values."""
    return [
        badge
        for match in matches
        if match.get("match_mode") == RANKED_MATCH_MODE
        and type(badge := match.get("ranked_display_badge")) is int
        and 10 <= badge <= 126
        and badge % 10 <= 6
    ]


def win_percentage(wins, losses):
    decided = wins + losses
    return float(round(wins / decided * 100, 1)) if decided else 0.0


@app.get("/api/player/{account_id}/matches")
async def get_player_matches(
    account_id: int,
    scope: str = Query(default="season1", pattern="^(all|season1)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if account_id < 0:
        raise HTTPException(status_code=422, detail="Account ID must be non-negative.")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.deadlock-api.com/v1/players/{account_id}/match-history"
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Player match history is unavailable."
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail="Match history could not be loaded. Please try again.",
                )
            raw_matches = response.json()
            matches = sorted(
                select_matches(raw_matches, scope),
                key=lambda match: (match["start_time"], match.get("match_id", 0)),
                reverse=True,
            )
            total = len(matches)
            ranked_badges = valid_rank_badges(matches)
            rank_badge = None
            if ranked_badges:
                rank_badge = max(ranked_badges) if scope == "all" else ranked_badges[0]
            all_time_badges = valid_rank_badges(raw_matches)
            start = (page - 1) * page_size
            selected = matches[start : start + page_size]
            heroes = {}
            if selected:
                try:
                    hero_response = await client.get(
                        "https://api.deadlock-api.com/v1/assets/heroes"
                    )
                    if hero_response.status_code == 200:
                        heroes = {
                            str(hero["id"]): hero["name"]
                            for hero in hero_response.json()
                        }
                except httpx.RequestError:
                    pass  # Keep the match list usable if hero names are temporarily unavailable.
            outcomes = {
                0: "Unknown",
                1: "Win",
                2: "Loss",
                3: "Penalized",
                4: "Party penalty",
                5: "Unscored",
            }
            modes = {
                0: "Unknown",
                1: "Unranked",
                2: "Private lobby",
                3: "Co-op bots",
                4: "Ranked",
                5: "Server test",
                6: "Tutorial",
                7: "Hero Labs",
                8: "Placement",
            }
            return {
                "accountId": str(account_id),
                "scope": scope,
                "page": page,
                "pageSize": page_size,
                "totalMatches": total,
                "totalPages": (total + page_size - 1) // page_size,
                "rankBadge": rank_badge,
                "highestRankBadge": max(all_time_badges, default=None),
                "matches": [
                    {
                        "matchId": match.get("match_id"),
                        "heroId": match.get("hero_id"),
                        "rankedBadge": match.get("ranked_display_badge")
                        if match.get("match_mode") == RANKED_MATCH_MODE
                        else None,
                        "startTime": match["start_time"],
                        "heroName": heroes.get(
                            str(match.get("hero_id")),
                            f"Hero {match.get('hero_id', '?')}",
                        ),
                        "mode": modes.get(match.get("match_mode"), "Unknown"),
                        "result": outcomes.get(
                            match.get("player_match_outcome"), "Unknown"
                        ),
                        "kills": match.get("player_kills"),
                        "deaths": match.get("player_deaths"),
                        "assists": match.get("player_assists"),
                        "souls": match.get("net_worth"),
                        "durationSeconds": match.get("match_duration_s"),
                    }
                    for match in selected
                ],
            }
        except httpx.RequestError:
            raise HTTPException(
                status_code=502, detail="The Deadlock API could not be reached."
            )


# Dependency to open/close safe database sessions automatically per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"status": "Online", "database": "Connected to Docker"}


@app.get("/api/player/search")
async def search_players(query: str = Query(min_length=1, max_length=100)):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a player name.")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.deadlock-api.com/v1/players/steam-search",
                params={
                    "search_query": query,
                    "limit": 100,
                    "min_matches_played_last_30d": 0,
                    "matches_played_weight": 0,
                },
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="No Steam players found.")
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Player search is temporarily unavailable."
                )
            # Stable sort keeps the upstream similarity order within each group.
            normalized_query = query.casefold()
            players = sorted(
                response.json(),
                key=lambda player: (
                    player["personaname"].casefold() != normalized_query,
                    not player["personaname"].casefold().startswith(normalized_query),
                    normalized_query not in player["personaname"].casefold(),
                ),
            )[:10]
            return {
                "players": [
                    {
                        "accountId": player["account_id"],
                        "playerName": player["personaname"],
                        "avatar": player["avatar"],
                    }
                    for player in players
                ]
            }
        except httpx.RequestError as e:
            logger.warning("Player search request failed: %s", e)
            raise HTTPException(
                status_code=502, detail="The Deadlock API could not be reached."
            )


@app.get("/api/player/{account_id}/summary")
async def get_player_performance(
    account_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: str = Query(default="season1", pattern="^(all|season1)$"),
):
    scope_key = scope.lower()
    season_only = scope_key == "season1"
    unscored_cutoff = int(time.time()) - UNSCORED_LOOKBACK_SECONDS

    # Reuse the seasonal summary only while its unscored lookback remains valid.
    cached_record = (
        db.query(PlayerStat).filter(PlayerStat.account_id == account_id).first()
    )
    if (
        cached_record
        and season_only
        and unscored_cutoff <= SEASON_1_START
        and cached_record.season == SEASON_1
        and not cached_record.dominant_hero.isdigit()
    ):
        logger.info("Serving cached player metrics: %s", account_id)
        win_rate = win_percentage(cached_record.wins or 0, cached_record.losses or 0)
        cached_record.win_rate = win_rate
        db.commit()
        return {
            "accountId": cached_record.account_id,
            "scope": scope_key,
            "metrics": {
                "totalMatches": cached_record.total_matches,
                "wins": cached_record.wins,
                "losses": cached_record.losses,
                "unscored": cached_record.unscored,
                "winRatePercentage": win_rate,
                "killDeathRatio": cached_record.kill_death_ratio,
                "avgSoulsCollected": cached_record.avg_souls,
                "dominantHero": cached_record.dominant_hero,
                "dominantHeroMatches": cached_record.dominant_hero_matches,
                "overallMostPlayedHero": cached_record.overall_hero,
                "overallMostPlayedHeroMatches": cached_record.overall_hero_matches,
            },
        }

    # Otherwise calculate metrics from the upstream match history.
    logger.info("Loading player metrics: %s (%s)", account_id, scope_key)

    async with httpx.AsyncClient() as client:
        try:
            api_url = (
                f"https://api.deadlock-api.com/v1/players/{account_id}/match-history"
            )
            response = await client.get(api_url)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=404,
                    detail="Player telemetry timeline missing or profile set to private.",
                )

            raw_matches = response.json()

            if not raw_matches:
                raise HTTPException(
                    status_code=404,
                    detail="No public competitive matches recorded for this ID.",
                )

            heroes_response = await client.get(
                "https://api.deadlock-api.com/v1/assets/heroes"
            )
            hero_names = (
                {str(hero["id"]): hero["name"] for hero in heroes_response.json()}
                if heroes_response.status_code == 200
                else {}
            )

            overall_hero_counts = pd.Series(
                match["hero_id"]
                for match in raw_matches
                if match.get("hero_id") is not None
            ).value_counts()
            overall_hero_id = (
                str(overall_hero_counts.idxmax())
                if not overall_hero_counts.empty
                else "Unknown"
            )
            overall_hero_matches = (
                int(overall_hero_counts.max()) if not overall_hero_counts.empty else 0
            )
            overall_hero = hero_names.get(overall_hero_id, overall_hero_id)

            filtered_matches = select_matches(raw_matches, scope_key)

            if not filtered_matches:
                return {
                    "accountId": account_id,
                    "scope": scope_key,
                    "hasRankedMatches": False,
                    "message": "No matches recorded for this player in the selected scope.",
                    "metrics": {
                        "totalMatches": 0,
                        "wins": 0,
                        "losses": 0,
                        "unscored": 0,
                        "winRatePercentage": None,
                        "killDeathRatio": None,
                        "avgSoulsCollected": None,
                        "dominantHero": "Unknown",
                        "dominantHeroMatches": 0,
                        "overallMostPlayedHero": overall_hero,
                        "overallMostPlayedHeroMatches": overall_hero_matches,
                    },
                }

            df = pd.DataFrame(filtered_matches)
            wins = int(df["player_match_outcome"].eq(1).sum())
            losses = int(df["player_match_outcome"].eq(2).sum())
            unscored = int(
                (
                    df["player_match_outcome"].ne(1)
                    & df["player_match_outcome"].ne(2)
                    & df["start_time"].ge(unscored_cutoff)
                ).sum()
            )
            total_matches = len(filtered_matches)
            win_rate = win_percentage(wins, losses)
            total_kills = int(df["player_kills"].sum())
            total_deaths = int(df["player_deaths"].sum())
            kill_death_ratio = (
                float(round(total_kills / total_deaths, 2))
                if total_deaths
                else float(total_kills)
            )
            avg_souls = (
                int(df["net_worth"].mean())
                if "net_worth" in df.columns and not df.empty
                else 0
            )
            hero_match_counts = df["hero_id"].value_counts()
            favorite_hero_id = (
                str(hero_match_counts.idxmax())
                if not hero_match_counts.empty
                else "Unknown"
            )
            favorite_hero_matches = (
                int(hero_match_counts.max()) if not hero_match_counts.empty else 0
            )
            favorite_hero = hero_names.get(favorite_hero_id, favorite_hero_id)

            if season_only:
                values = {
                    "total_matches": total_matches,
                    "wins": wins,
                    "losses": losses,
                    "unscored": unscored,
                    "win_rate": win_rate,
                    "kill_death_ratio": kill_death_ratio,
                    "avg_souls": avg_souls,
                    "dominant_hero": favorite_hero,
                    "dominant_hero_matches": favorite_hero_matches,
                    "overall_hero": overall_hero,
                    "overall_hero_matches": overall_hero_matches,
                    "season": SEASON_1,
                }
                if cached_record:
                    for field, value in values.items():
                        setattr(cached_record, field, value)
                else:
                    db.add(PlayerStat(account_id=account_id, **values))
            db.commit()
            logger.info("Player metrics processed: %s (%s)", account_id, scope_key)

            return {
                "accountId": account_id,
                "scope": scope_key,
                "hasRankedMatches": bool(filtered_matches),
                "metrics": {
                    "totalMatches": total_matches,
                    "wins": wins,
                    "losses": losses,
                    "unscored": unscored,
                    "winRatePercentage": win_rate,
                    "killDeathRatio": kill_death_ratio,
                    "avgSoulsCollected": avg_souls,
                    "dominantHero": favorite_hero,
                    "dominantHeroMatches": favorite_hero_matches,
                    "overallMostPlayedHero": overall_hero,
                    "overallMostPlayedHeroMatches": overall_hero_matches,
                },
            }

        except HTTPException:
            db.rollback()
            raise
        except httpx.RequestError as e:
            db.rollback()
            logger.warning("Player telemetry request failed: %s", e)
            raise HTTPException(
                status_code=502, detail="The Deadlock API could not be reached."
            )
        except Exception as e:
            db.rollback()
            logger.exception("Player telemetry processing failed")
            raise HTTPException(status_code=500, detail=f"Pipeline Failure: {e!s}")
