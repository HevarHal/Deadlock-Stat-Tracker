import httpx # type: ignore
import pandas as pd # type: ignore
import time
from fastapi import FastAPI, HTTPException, Depends, Query # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from sqlalchemy.orm import Session # type: ignore
from database import SessionLocal, PlayerStat, init_db

app = FastAPI(title="Deadlock Live Analytics Pipeline")

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

SEASON_1 = "season_1_player_outcomes_v7"
SEASON_1_START = 1785430800
SEASON_1_END = 1793854800
RANKED_MATCH_MODE = 4
UNSCORED_LOOKBACK_SECONDS = 90 * 24 * 60 * 60

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
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.deadlock-api.com/v1/players/steam-search",
                params={"search_query": query, "limit": 10},
            )
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="No Steam players found.")
            return {
                "players": [
                    {
                        "accountId": player["account_id"],
                        "playerName": player["personaname"],
                        "avatar": player["avatar"],
                    }
                    for player in response.json()
                ]
            }
        except HTTPException:
            raise
        except httpx.RequestError as e:
            print("!!! PLAYER SEARCH FAILED !!!:", str(e))
            raise HTTPException(status_code=502, detail="The Deadlock API could not be reached.")

@app.get("/api/player/{account_id}/summary")
async def get_player_performance(
    account_id: str,
    scope: str = Query(default="season1", regex="^(all|season1)$"),
    db: Session = Depends(get_db)
):
    scope_key = scope.lower()
    season_only = scope_key == "season1"
    unscored_cutoff = int(time.time()) - UNSCORED_LOOKBACK_SECONDS

    # 1. Performance Cache Optimization Check (Queries Docker Postgres)
    cached_record = db.query(PlayerStat).filter(PlayerStat.account_id == account_id).first()
    if (
        cached_record
        and season_only
        and unscored_cutoff <= SEASON_1_START
        and cached_record.season == SEASON_1
        and not cached_record.dominant_hero.isdigit()
    ):
        print(f"--- [CACHE HIT] Fetching user {account_id} metrics from Docker PostgreSQL ---")
        decided_matches = (cached_record.wins or 0) + (cached_record.losses or 0)
        win_rate = float(round((cached_record.wins / decided_matches) * 100, 1)) if decided_matches else 0.0
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
                "overallMostPlayedHeroMatches": cached_record.overall_hero_matches
            }
        }

    # 2. [CACHE MISS] Extracting accurate game telemetry from live community servers
    print(f"--- [CACHE MISS] Ingesting match metrics from live API for ID: {account_id} ({scope_key}) ---")



    async with httpx.AsyncClient() as client:
        try:
            api_url = f"https://api.deadlock-api.com/v1/players/{account_id}/match-history"
            response = await client.get(api_url)

            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Player telemetry timeline missing or profile set to private.")

            raw_matches = response.json()

            if not raw_matches:
                raise HTTPException(status_code=404, detail="No public competitive matches recorded for this ID.")

            heroes_response = await client.get("https://api.deadlock-api.com/v1/assets/heroes")
            hero_names = {
                str(hero["id"]): hero["name"]
                for hero in heroes_response.json()
            } if heroes_response.status_code == 200 else {}

            overall_hero_counts = pd.Series(
                match["hero_id"] for match in raw_matches if match.get("hero_id") is not None
            ).value_counts()
            overall_hero_id = str(overall_hero_counts.idxmax()) if not overall_hero_counts.empty else "Unknown"
            overall_hero_matches = int(overall_hero_counts.max()) if not overall_hero_counts.empty else 0
            overall_hero = hero_names.get(overall_hero_id, overall_hero_id)

            filtered_matches = [
                match for match in raw_matches
                if match.get("match_mode") == RANKED_MATCH_MODE and (
                    not season_only or SEASON_1_START <= match["start_time"] < SEASON_1_END
                )
            ] if scope_key == "all" else [
                match for match in raw_matches
                if match.get("match_mode") == RANKED_MATCH_MODE and SEASON_1_START <= match["start_time"] < SEASON_1_END
            ]

            if not filtered_matches:
                return {
                    "accountId": account_id,
                    "scope": scope_key,
                    "hasRankedMatches": False,
                    "message": "No ranked matches recorded for this player in the selected scope.",
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
                        "overallMostPlayedHeroMatches": overall_hero_matches
                    }
                }

            df = pd.DataFrame(filtered_matches)
            wins = int(df["player_match_outcome"].eq(1).sum())
            losses = int(df["player_match_outcome"].eq(2).sum())
            unscored = int((
                df["player_match_outcome"].ne(1)
                & df["player_match_outcome"].ne(2)
                & df["start_time"].ge(unscored_cutoff)
            ).sum())
            total_matches = wins + losses
            decided_matches = wins + losses
            win_rate = float(round((wins / decided_matches) * 100, 1)) if decided_matches else 0.0
            total_kills = int(df["player_kills"].sum())
            total_deaths = int(df["player_deaths"].sum())
            kda = float(round(total_kills / total_deaths, 2)) if total_deaths else float(total_kills)
            avg_souls = int(df['net_worth'].mean()) if 'net_worth' in df.columns and not df.empty else 0
            hero_match_counts = df["hero_id"].value_counts()
            favorite_hero_id = str(hero_match_counts.idxmax()) if not hero_match_counts.empty else "Unknown"
            favorite_hero_matches = int(hero_match_counts.max()) if not hero_match_counts.empty else 0
            favorite_hero = hero_names.get(favorite_hero_id, favorite_hero_id)

            if cached_record and season_only:
                cached_record.total_matches = total_matches
                cached_record.wins = wins
                cached_record.losses = losses
                cached_record.unscored = unscored
                cached_record.win_rate = win_rate
                cached_record.kill_death_ratio = kda
                cached_record.avg_souls = avg_souls
                cached_record.dominant_hero = favorite_hero
                cached_record.dominant_hero_matches = favorite_hero_matches
                cached_record.overall_hero = overall_hero
                cached_record.overall_hero_matches = overall_hero_matches
                cached_record.season = SEASON_1
            elif not cached_record and season_only:
                db.add(PlayerStat(
                    account_id=account_id,
                    total_matches=total_matches,
                    wins=wins,
                    losses=losses,
                    unscored=unscored,
                    win_rate=win_rate,
                    kill_death_ratio=kda,
                    avg_souls=avg_souls,
                    dominant_hero=favorite_hero,
                    dominant_hero_matches=favorite_hero_matches,
                    overall_hero=overall_hero,
                    overall_hero_matches=overall_hero_matches,
                    season=SEASON_1
                ))
            db.commit()
            print("--- Live metrics processed successfully and written to Docker Storage! ---")

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
                    "killDeathRatio": kda,
                    "avgSoulsCollected": avg_souls,
                    "dominantHero": favorite_hero,
                    "dominantHeroMatches": favorite_hero_matches,
                    "overallMostPlayedHero": overall_hero,
                    "overallMostPlayedHeroMatches": overall_hero_matches
                }
            }

        except HTTPException:
            db.rollback()
            raise
        except httpx.RequestError as e:
            db.rollback()
            print("!!! LIVE API REQUEST FAILED !!!:", str(e))
            raise HTTPException(status_code=502, detail="The Deadlock API could not be reached.")
        except Exception as e:
            db.rollback()
            print("!!! DATA PIPELINE CRASH DETAIL !!!:", str(e))
            raise HTTPException(status_code=500, detail=f"Pipeline Failure: {str(e)}")
