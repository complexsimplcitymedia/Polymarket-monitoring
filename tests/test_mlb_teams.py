import pytest

from src.backend.sports.mlb_context import Game
from src.backend.sports.mlb_teams import biggest_swing, build_rows, quality_split, rank_map, win_pcts


def g(day, away, home, ar, hr):
    return Game(day, away, home, ar, hr)


def test_rank_map_best_first_and_ties_share_a_rank():
    assert rank_map({"a": 5.0, "b": 3.0, "c": 3.0, "d": 1.0}, higher_is_better=True) == {"a": 1, "b": 2, "c": 2, "d": 4}
    assert rank_map({"a": 5.0, "b": 3.0}, higher_is_better=False) == {"b": 1, "a": 2}


GAMES = [
    g("2026-09-01", "Good", "Bad", 5, 1),   # Good beats Bad
    g("2026-09-02", "Good", "Mid", 2, 3),   # Mid beats Good
    g("2026-09-03", "Mid", "Bad", 4, 0),    # Mid beats Bad
    g("2026-09-04", "Mid", "Good", 1, 6),   # Good beats Mid
    g("2026-09-05", "Bad", "Good", 0, 9),   # Good beats Bad
]


def test_quality_split_counts_by_opponent_strength():
    pct = win_pcts(GAMES)
    q = quality_split(GAMES, "Good", pct, top={"Mid", "Good"}, bottom={"Bad"})
    assert q["vs_bottom_10"] == [2, 0]  # two wins over Bad
    assert q["vs_top_12"] == [1, 1]  # one win and one loss against Mid
    assert q["avg_opponent_pct"] == pytest.approx((pct["Bad"] + pct["Mid"] + pct["Mid"] + pct["Bad"]) / 4)


def test_biggest_swing_finds_best_and_worst_windows():
    games = [g(f"2026-09-{i:02d}", "T", "X", 3, 1) for i in range(1, 6)] + \
            [g(f"2026-09-{i:02d}", "T", "X", 1, 3) for i in range(6, 11)]
    s = biggest_swing(games, "T", window=5)
    assert s["best"] == [5, 0] and s["worst"] == [0, 5]
    assert biggest_swing(games[:3], "T", window=5) is None


def stat(rpg=4.0, ops=0.7, avg=0.25, era=4.0, whip=1.3, fld=0.985, errors_pg=0.5):
    return dict(rpg=rpg, ops=ops, avg=avg, era=era, whip=whip, fld=fld, errors_pg=errors_pg)


def test_build_rows_has_ranks_form_and_september_record():
    season = {"Good": stat(rpg=5.0, era=3.0), "Mid": stat(), "Bad": stat(rpg=3.0, era=5.0)}
    sept = {"Good": stat(rpg=6.0), "Mid": stat(), "Bad": stat(rpg=2.0)}
    rows = build_rows(GAMES, ["Good"], {"Good": 1}, season, sept)
    r = rows[0]
    assert r["team"] == "Good" and r["record"]["wins"] == 3 and r["record"]["losses"] == 1
    assert r["season"]["rpg"]["rank"] == 1 and r["season"]["era"]["rank"] == 1  # best offense and lowest ERA
    assert r["sept"]["rpg"]["value"] == 6.0
    assert r["september"] == {"wins": 3, "losses": 1}
    assert r["form"]["last_10"]["wins"] == 3 and "last_50" in r["form"]


def test_build_rows_skips_teams_without_data_and_flags_california():
    rows = build_rows(GAMES, ["Nobody"], {}, {"Good": stat()}, {"Good": stat()})
    assert rows == []
    games = [g("2026-09-01", "Los Angeles Dodgers", "Mid", 3, 1)]
    st = {"Los Angeles Dodgers": stat(), "Mid": stat()}
    assert build_rows(games, ["Los Angeles Dodgers"], {}, st, st)[0]["california"] is True
