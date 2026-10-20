import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, PlayerStat, init_db

app = FastAPI(title="Deadlock Live Analytics Pipeline")

# Boots up database structures inside Docker on app launch
init_db()

#origins=[ frontend] 
#fix this to be secure and only access backend 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #allow_origins=["*"] 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SEASON_1 = "season_1_player_outcomes_v7"
SEASON_1_START = 1785430800
SEASON_1_END = 1791493200
RANKED_MATCH_MODE = 4

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
async def get_player_performance(account_id: str, db: Session = Depends(get_db)):
    # 1. Performance Cache Optimization Check (Queries Docker Postgres)
    cached_record = db.query(PlayerStat).filter(PlayerStat.account_id == account_id).first()
    if cached_record and cached_record.season == SEASON_1 and not cached_record.dominant_hero.isdigit():
        print(f"--- [CACHE HIT] Fetching user {account_id} metrics from Docker PostgreSQL ---")
        return {
            "accountId": cached_record.account_id,
            "metrics": {
                "totalMatches": cached_record.total_matches,
                "wins": cached_record.wins,
                "losses": cached_record.losses,
                "unscored": cached_record.unscored,
                "winRatePercentage": cached_record.win_rate,
                "killDeathRatio": cached_record.kill_death_ratio,
                "avgSoulsCollected": cached_record.avg_souls,
                "dominantHero": cached_record.dominant_hero,
                "dominantHeroMatches": cached_record.dominant_hero_matches,
                "overallMostPlayedHero": cached_record.overall_hero,
                "overallMostPlayedHeroMatches": cached_record.overall_hero_matches
            }
        }

    # 2. [CACHE MISS] Extracting accurate game telemetry from live community servers
    print(f"--- [CACHE MISS] Ingesting match metrics from live API for ID: {account_id} ---")
    
    # Use a current public profile when the legacy template placeholder is used.
    target_id = "76561198395093892" if account_id == "76561198000000000" else account_id

    async with httpx.AsyncClient() as client:
        try:
            # Fetch the player's stored match history from the official API.
            api_url = f"https://api.deadlock-api.com/v1/players/{target_id}/match-history"
            response = await client.get(api_url)
            
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Player telemetry timeline missing or profile set to private.")
            
            raw_matches = response.json()
            
            if not raw_matches:
                raise HTTPException(status_code=404, detail="No public competitive matches recorded for this ID.")
    
            # 3. Transforming and cleaning actual live data records with Pandas
            heroes_response = await client.get("https://api.deadlock-api.com/v1/assets/heroes")
            hero_names = {
                str(hero["id"]): hero["name"]
                for hero in heroes_response.json()
            } if heroes_response.status_code == 200 else {}

            overall_hero_counts = pd.Series(
                match["hero_id"] for match in raw_matches if match.get("hero_id") is not None
            ).value_counts()
            overall_hero_id = str(overall_hero_counts.idxmax())
            overall_hero_matches = int(overall_hero_counts.max())
            overall_hero = hero_names.get(overall_hero_id, overall_hero_id)
            
            season_matches = [
                match for match in raw_matches
                if SEASON_1_START <= match["start_time"] < SEASON_1_END
                and match["match_mode"] == RANKED_MATCH_MODE
            ]
            if not season_matches:
                raise HTTPException(status_code=404, detail="No ranked Season 1 matches recorded for this player.")

            # The API returns one match-history entry per row.
            df = pd.DataFrame(season_matches)
            total_matches = len(df)
            wins = int(df["player_match_outcome"].eq(1).sum())
            losses = int(df["player_match_outcome"].eq(2).sum())
            unscored = total_matches - wins - losses
            win_rate = float(round((wins / total_matches) * 100, 1)) if total_matches else 0.0
            total_kills = int(df["player_kills"].sum())
            total_deaths = int(df["player_deaths"].sum())
            kda = float(round(total_kills / total_deaths, 2)) if total_deaths else float(total_kills)
            avg_souls = int(df['net_worth'].mean())
            hero_match_counts = df["hero_id"].value_counts()
            favorite_hero_id = str(hero_match_counts.idxmax())
            favorite_hero_matches = int(hero_match_counts.max())
            favorite_hero = hero_names.get(favorite_hero_id, favorite_hero_id)

            # 4. Commit results permanently to Docker persistence layers to create a cache history
            if cached_record:
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
            else:
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
