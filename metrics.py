"""Pure O(n) player-summary calculations without DataFrame allocation."""
from collections import Counter
import math


def most_played_hero(matches):
    """Return the hero ID and count; ties keep the first hero encountered."""
    counts = Counter(m["hero_id"] for m in matches if m.get("hero_id") is not None)
    if not counts:
        return "Unknown", 0
    hero, count = counts.most_common(1)[0]
    return str(hero), count


def calculate_metrics(matches, unscored_cutoff):
    """Accumulate totals in one pass, ignoring missing soul values."""
    wins = losses = unscored = 0
    kills = deaths = 0
    souls = souls_count = 0
    for match in matches:
        outcome = match.get("player_match_outcome")
        wins += outcome == 1
        losses += outcome == 2
        if outcome not in (1, 2) and match["start_time"] >= unscored_cutoff:
            unscored += 1
        kills += match.get("player_kills") or 0
        deaths += match.get("player_deaths") or 0
        worth = match.get("net_worth")
        if worth is not None and math.isfinite(worth):
            souls += worth
            souls_count += 1
    return {
        "total_matches": len(matches),
        "wins": wins,
        "losses": losses,
        "unscored": unscored,
        "kill_death_ratio": float(round(kills / deaths, 2)) if deaths else float(kills),
        "avg_souls": int(souls / souls_count) if souls_count else 0,
    }
