from src.backend.sports.cfb import (
    LiveGame,
    TeamState,
    evaluate,
    label_favorite,
    match_market,
    norm,
    outcome_prices,
    parse_scoreboard,
    parse_summary,
)


def team(name, abbr, score=0, rank=None, w=3, l=1):
    return TeamState(name=name, abbr=abbr, score=score, rank=rank, wins=w, losses=l)


def game(home, away):
    return LiveGame(event_id="1", start=None, detail="Q4", home=home, away=away)


def comp(side, loc, abbr, score, rank=99, rec="3-1"):
    return {
        "homeAway": side, "score": str(score), "curatedRank": {"current": rank},
        "team": {"location": loc, "abbreviation": abbr},
        "records": [{"type": "total", "summary": rec}],
    }


def test_norm_expands_st_and_strips_punctuation():
    assert norm("NC St.") == norm("NC State") == "nc state"
    assert norm("Texas A&M") == "texas a and m"


def test_parse_scoreboard_keeps_only_live_games():
    payload = {"events": [
        {"id": "1", "date": "2026-10-03T16:00Z", "competitions": [{
            "status": {"type": {"state": "in", "shortDetail": "Q4"}},
            "competitors": [comp("home", "Minnesota", "MINN", 20, rec="4-1"),
                            comp("away", "Michigan", "MICH", 14, rank=12)]}]},
        {"id": "2", "competitions": [{
            "status": {"type": {"state": "post", "shortDetail": "Final"}},
            "competitors": [comp("home", "A", "A", 1), comp("away", "B", "B", 0)]}]},
    ]}
    games = parse_scoreboard(payload)
    assert [g.event_id for g in games] == ["1"]
    assert games[0].away.rank == 12 and games[0].home.rank is None  # 99 = unranked
    assert games[0].home.wins == 4


def test_parse_summary_takes_latest_win_prob_and_spread():
    s = {"winprobability": [{"homeWinPercentage": 0.2}, {"homeWinPercentage": 0.85}],
         "pickcenter": [{"details": "MICH -6.5"}]}
    assert parse_summary(s) == (0.85, "MICH -6.5")
    assert parse_summary({}) == (None, None)


def test_label_favorite_prefers_spread_then_rank_then_record():
    g = game(team("Minnesota", "MINN"), team("Michigan", "MICH"))
    assert label_favorite(g, "MICH -6.5") == ("Michigan", "spread MICH -6.5")
    g = game(team("A", "A", rank=None), team("B", "B", rank=12))
    assert label_favorite(g, None) == ("B", "rank")
    g = game(team("Idaho", "IDHO", w=0, l=5), team("Montana State", "MTST", w=5, l=0))
    assert label_favorite(g, None) == ("Montana State", "record")
    g = game(team("A", "A"), team("B", "B"))
    assert label_favorite(g, None) == (None, "none")


def test_match_market_by_outcome_names():
    g = game(team("Idaho", "IDHO"), team("Montana State", "MTST"))
    m = {"outcomes": '["Montana State", "Idaho"]', "slug": "cfb-x"}
    assert match_market(g, [{"outcomes": '["A","B"]'}, m]) is m
    assert match_market(g, [{"outcomes": '["A","B"]'}]) is None


def test_outcome_prices_maps_names_to_floats():
    m = {"outcomes": '["Minnesota", "Michigan"]', "outcomePrices": '["0.71", "0.29"]'}
    assert outcome_prices(m) == {"Minnesota": 0.71, "Michigan": 0.29}


def test_evaluate_flags_underpriced_leader_late_game():
    # Minnesota up 20-14 late: ESPN 85%, market 71%; Michigan was the label favorite
    g = game(team("Minnesota", "MINN", 20), team("Michigan", "MICH", 14))
    sigs = evaluate(g, 0.85, {"Minnesota": 0.71, "Michigan": 0.29}, "MICH -6.5", "cfb-m")
    assert [s.team for s in sigs] == ["Minnesota"]
    assert sigs[0].gap == 0.85 - 0.71 or abs(sigs[0].gap - 0.14) < 1e-9
    assert sigs[0].is_label_underdog and sigs[0].label_basis.startswith("spread")


def test_evaluate_ignores_gap_below_threshold_and_missing_prices():
    g = game(team("Minnesota", "MINN", 20), team("Michigan", "MICH", 14))
    assert evaluate(g, 0.85, {"Minnesota": 0.80, "Michigan": 0.20}, None, "s") == []
    assert evaluate(g, 0.85, {"Other": 0.1}, None, "s") == []


def test_candidate_slugs_filters_by_both_team_names_newest_first():
    from src.backend.sports.cfb import candidate_slugs

    g = game(team("Idaho", "IDHO"), team("Montana State", "MTST"))
    markets = [
        ("cfb-monst-idaho-2026-10-02", "Montana State vs. Idaho"),
        ("cfb-monst-idaho-2025-10-01", "Montana State vs. Idaho"),
        ("cfb-minnst-wash-2026-09-26", "Minnesota vs. Washington"),
    ]
    assert candidate_slugs(g, markets) == [
        "cfb-monst-idaho-2026-10-02", "cfb-monst-idaho-2025-10-01"
    ]
