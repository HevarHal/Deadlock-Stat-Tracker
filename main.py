import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import PlayerStat, SessionLocal, init_db
from match_details import router as match_details_router
from metrics import calculate_metrics, most_played_hero
from upstream import (
    API_BASE,
    MATCH_CACHE_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    UpstreamClient,
    client_for,
    fetch_hero_names,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(init_db)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        app.state.upstream = UpstreamClient(client)
        try:
            yield
        finally:
            await app.state.upstream.close()
            del app.state.upstream


app = FastAPI(title="Deadlock Live Analytics Pipeline", lifespan=lifespan)
app.include_router(match_details_router)

# Permit the deployed frontend; development uses Vite's same-origin API proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://deadlocktracker.ca"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

SEASON_1_CACHE_VERSION = "season_1_player_outcomes_v9"
SEASON_1_START = 1785430800
SEASON_1_END = 1793854800
RANKED_MATCH_MODE = 4
STREET_BRAWL_GAME_MODE = 4
UNSCORED_LOOKBACK_SECONDS = 90 * 24 * 60 * 60


MATCH_OUTCOMES = {
    0: "Unknown",
    1: "Win",
    2: "Loss",
    3: "Penalized",
    4: "Party penalty",
    5: "Unscored",
}
MATCH_MODES = {
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

SUMMARY_FIELDS = {
    "totalMatches": "total_matches",
    "wins": "wins",
    "losses": "losses",
    "unscored": "unscored",
    "winRatePercentage": "win_rate",
    "killDeathRatio": "kill_death_ratio",
    "avgSoulsCollected": "avg_souls",
    "dominantHero": "dominant_hero",
    "dominantHeroMatches": "dominant_hero_matches",
    "overallMostPlayedHero": "overall_hero",
    "overallMostPlayedHeroMatches": "overall_hero_matches",
}


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
    request: Request,
    account_id: int,
    scope: str = Query(default="season1", pattern="^(all|season1)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if account_id < 0:
        raise HTTPException(status_code=422, detail="Account ID must be non-negative.")
    async with client_for(request) as client:
        try:
            response = await client.get(
                f"{API_BASE}/players/{account_id}/match-history"
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
            all_time_badges = (
                ranked_badges if scope == "all" else valid_rank_badges(raw_matches)
            )
            start = (page - 1) * page_size
            selected = matches[start : start + page_size]
            heroes = await fetch_hero_names(client) if selected else {}
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
                        "mode": (
                            "Street Brawl"
                            if match.get("game_mode") == STREET_BRAWL_GAME_MODE
                            else MATCH_MODES.get(match.get("match_mode"), "Unknown")
                        ),
                        "result": MATCH_OUTCOMES.get(
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


def get_db():
    """Provide a database session and close it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"status": "Online", "database": "Connected to Docker"}


@app.get("/api/player/search")
async def search_players(request: Request, query: str = Query(min_length=1, max_length=100)):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a player name.")
    async with client_for(request) as client:
        try:
            response = await client.get(
                f"{API_BASE}/players/steam-search",
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

            def search_priority(player):
                name = player["personaname"].casefold()
                return (
                    name != normalized_query,
                    not name.startswith(normalized_query),
                    normalized_query not in name,
                )

            players = sorted(
                response.json(),
                key=search_priority,
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
def utc_now():
    # The existing PostgreSQL column stores UTC without a timezone suffix.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def summary_response(account_id, scope, values):
    response = {
        "accountId": str(account_id),
        "scope": scope,
        "hasRankedMatches": bool(values["total_matches"]),
        "metrics": {key: values[field] for key, field in SUMMARY_FIELDS.items()},
    }
    if not values["total_matches"]:
        response["message"] = "No matches recorded for this player in the selected scope."
    return response


def read_cached_summary(db, account_id):
    """Complete the read transaction before any upstream network waits."""
    try:
        record = db.query(PlayerStat).filter(PlayerStat.account_id == account_id).first()
        now = utc_now()
        oldest_allowed = now - timedelta(seconds=MATCH_CACHE_SECONDS)
        if (
            record
            and record.season == SEASON_1_CACHE_VERSION
            and record.updated_at is not None
            and oldest_allowed <= record.updated_at <= now
        ):
            return {field: getattr(record, field) for field in SUMMARY_FIELDS.values()}
        return None
    finally:
        db.rollback()


def save_summary(db, account_id, values, fetched_at):
    try:
        record = db.query(PlayerStat).filter(PlayerStat.account_id == account_id).first()
        values = {**values, "season": SEASON_1_CACHE_VERSION, "updated_at": fetched_at}
        if record:
            for field, value in values.items():
                setattr(record, field, value)
        else:
            db.add(PlayerStat(account_id=account_id, **values))
        db.commit()
    except Exception:
        db.rollback()
        raise


@app.get("/api/player/{account_id}/summary")
async def get_player_performance(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    account_id: int = Path(ge=0),
    scope: str = Query(default="season1", pattern="^(all|season1)$"),
):
    try:
        if scope == "season1":
            cached = await run_in_threadpool(read_cached_summary, db, str(account_id))
            if cached is not None:
                return summary_response(account_id, scope, cached)

        async with client_for(request) as client:
            response = await client.get(
                f"{API_BASE}/players/{account_id}/match-history"
            )
            if response.status_code == 404:
                raise HTTPException(404, "Player telemetry timeline missing or profile set to private.")
            if response.status_code != 200:
                raise HTTPException(502, "Player statistics are temporarily unavailable.")
            raw_matches = response.json()
            fetched_at = getattr(response, "fetched_at", utc_now())
            if not raw_matches:
                raise HTTPException(404, "No public competitive matches recorded for this ID.")

            hero_names = await fetch_hero_names(client)

        overall_id, overall_count = most_played_hero(raw_matches)
        selected = select_matches(raw_matches, scope)
        values = calculate_metrics(selected, int(time.time()) - UNSCORED_LOOKBACK_SECONDS)
        favorite_id, favorite_count = most_played_hero(selected)
        values.update({
            "win_rate": win_percentage(values["wins"], values["losses"]) if selected else None,
            "dominant_hero": hero_names.get(favorite_id, favorite_id),
            "dominant_hero_matches": favorite_count,
            "overall_hero": hero_names.get(overall_id, overall_id),
            "overall_hero_matches": overall_count,
        })
        if not selected:
            values["kill_death_ratio"] = values["avg_souls"] = None
        elif scope == "season1":
            await run_in_threadpool(save_summary, db, str(account_id), values, fetched_at)
        return summary_response(account_id, scope, values)
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.warning("Player telemetry request failed: %s", exc)
        raise HTTPException(502, "The Deadlock API could not be reached.") from exc
    except Exception as exc:
        logger.exception("Player telemetry processing failed")
        raise HTTPException(500, "Player statistics could not be processed.") from exc
