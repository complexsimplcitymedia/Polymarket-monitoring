import pytest

from src.backend.sports.football_teams import (
    FGame, build_rows, parse_schedule, parse_stats, per_game, rank_values, wl,
)


def competitor(tid, name, score, home, rank=99, winner=False):
    return {"team": {"id": tid, "displayName": name}, "homeAway": "home" if home else "away",
            "score": {"value": score}, "curatedRank": {"current": rank}, "winner": winner}


def event(date, mine, other, completed=True, neutral=False):
    return {"date": date, "competitions": [{"neutralSite": neutral, "status": {"type": {"completed": completed}},
                                            "competitors": [mine, other]}]}


def test_parse_schedule_splits_completed_and_next_and_reads_opponent_rank():
    payload = {"events": [
        event("2026-09-05", competitor("1", "A", 38, True), competitor("9", "B", 14, False, rank=12), True),
        event("2026-09-12", competitor("1", "A", 10, False), competitor("8", "C", 24, True), True, neutral=True),
        event("2026-09-19", competitor("1", "A", 0, True), competitor("7", "D", 0, False, rank=3), False),
    ]}
    games, nxt = parse_schedule(payload, "1")
    assert [g.opp_name for g in games] == ["B", "C"]
    assert games[0].opp_rank == 12 and games[1].opp_rank is None  # 99 means unranked
    assert games[0].home is True and games[1].home is None  # neutral site
    assert nxt["opponent"] == "D" and nxt["opp_rank"] == 3


def test_per_game_derives_turnovers_and_sacks():
    flat = {"rushing.teamGamesPlayed": 4.0, "rushing.totalYards": 1920.0, "defensive.sacks": 12.0,
            "defensiveInterceptions.interceptions": 3.0, "general.fumblesRecovered": 5.0,
            "passing.interceptions": 2.0, "rushing.rushingFumblesLost": 1.0, "receiving.receivingFumblesLost": 1.0}
    p = per_game(flat)
    assert p["yds"] == 480 and p["sacks"] == 3
    assert p["takeaways"] == 2 and p["giveaways"] == 1 and p["turnover_margin"] == 1
    assert per_game({})["yds"] is None


def test_parse_stats_flattens_categories():
    payload = {"results": {"stats": {"categories": [{"name": "passing", "stats": [{"name": "sacks", "value": 4}]},
                                                    {"name": "defensive", "stats": [{"name": "sacks", "value": 11}]}]}}}
    flat = parse_stats(payload)
    assert flat["passing.sacks"] == 4 and flat["defensive.sacks"] == 11  # kept apart by category


def test_rank_values_direction_and_ties():
    assert rank_values({"a": 3.0, "b": 3.0, "c": 1.0}, True) == {"a": 1, "b": 1, "c": 3}
    assert rank_values({"a": 3.0, "c": 1.0}, False) == {"c": 1, "a": 2}


def games_for(*results):  # (pf, pa, home, opp_id, opp_rank)
    return [FGame(f"2026-09-{i+1:02d}", o, f"opp{o}", h, pf, pa, r) for i, (pf, pa, h, o, r) in enumerate(results)]


def test_build_rows_record_form_quality_and_ranks():
    teams = {"1": {"name": "A", "group": "SEC"}, "2": {"name": "B", "group": "SEC"}}
    g = {"1": games_for((40, 10, True, "2", None), (30, 20, False, "9", 10), (14, 17, True, "2", None)),
         "2": games_for((10, 40, False, "1", None), (21, 3, True, "8", None), (17, 14, False, "1", None))}
    stats = {t: {"yds": 400.0 if t == "1" else 300.0, "sacks": 2.0, "takeaways": 1.0, "giveaways": 1.0, "turnover_margin": 0.0} for t in g}
    rows = {r["team"]: r for r in build_rows(teams, g, stats, {}, {"1": 4})}
    a = rows["A"]
    assert a["record"]["wins"] == 2 and a["record"]["losses"] == 1 and a["ap_rank"] == 4
    assert a["form"]["last_3"] == [2, 1] and a["splits"]["home"] == [1, 1] and a["splits"]["road"] == [1, 0]
    assert a["quality"]["vs_ranked"] == [1, 0]  # beat the one ranked opponent
    assert a["offense"]["yds"]["rank"] == 1 and rows["B"]["offense"]["yds"]["rank"] == 2
    assert a["conference"] == "SEC" and a["diff"]["value"] == pytest.approx((84 - 47) / 3)
    # one opponent ("9") is outside the league: the average covers only known teams and says so
    assert a["quality"]["outside_league"] == [1, 0] and a["quality"]["known_games"] == 2


def test_wl():
    assert wl(games_for((1, 0, True, "x", None), (0, 1, True, "x", None), (2, 0, True, "x", None))) == [2, 1]
