import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text # type: ignore
from sqlalchemy.orm import declarative_base, sessionmaker # type: ignore

# Targets the database running inside your Docker container
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PlayerStat(Base):
    __tablename__ = "player_stats"

    account_id = Column(String, primary_key=True, index=True)
    total_matches = Column(Integer)
    wins = Column(Integer)
    losses = Column(Integer)

    unscored = Column(Integer)
    win_rate = Column(Float)
    # Keep the existing database column name so current PostgreSQL tables remain compatible.
    kill_death_ratio = Column("avg_kills", Float)
    avg_souls = Column(Integer)
    dominant_hero = Column(String)
    dominant_hero_matches = Column(Integer)
    overall_hero = Column(String)
    overall_hero_matches = Column(Integer)
    season = Column(String)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = 'player_stats' AND table_schema = 'public'")
        ).first()

        if not table_exists:
            return

        existing_columns = {
            row[0] for row in connection.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'player_stats' AND table_schema = 'public'")
            )
        }

        column_definitions = {
            "account_id": "VARCHAR",
            "total_matches": "INTEGER",
            "wins": "INTEGER",
            "losses": "INTEGER",
            "unscored": "INTEGER",
            "win_rate": "DOUBLE PRECISION",
            "avg_kills": "DOUBLE PRECISION",
            "avg_souls": "INTEGER",
            "dominant_hero": "VARCHAR",
            "dominant_hero_matches": "INTEGER",
            "overall_hero": "VARCHAR",
            "overall_hero_matches": "INTEGER",
            "season": "VARCHAR",
            "updated_at": "TIMESTAMP",
        }

        for column_name, column_type in column_definitions.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
                )
