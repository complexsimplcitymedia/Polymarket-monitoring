from datetime import datetime, timedelta

from src.backend.sports.alerts import improved, confirmed, in_cooldown, message_for, priority_for, standing, verdict
from src.backend.sports.cfb import LiveGame, Signal, TeamState


def game(away_score, home_score):
    away = TeamState("Kentucky", "KY", away_score, None, 3, 1)
    home = TeamState("South Carolina", "SC", home_score, None, 3, 1)
    return LiveGame(event_id="42", start=None, detail="3rd 10:00", home=home, away=away)


def signal(team, wp, price, away_score=25, home_score=20, favorite="South Carolina"):
    return Signal(game(away_score, home_score), team, wp, price, wp - price, favorite, "spread SC -2.5", "cfb-uk-sc")


def test_alert_only_when_ahead_and_still_priced_to_lose():
    assert priority_for(signal("Kentucky", 0.58, 0.45), 0.5) == "normal"       # ahead 24-20, market has it at 45%
    assert priority_for(signal("Kentucky", 0.70, 0.60), 0.5) is None           # ahead but the market already favors it
    assert priority_for(signal("Kentucky", 0.70, 0.50), 0.5) is None           # exactly 50% is not "weighted to lose"
    assert priority_for(signal("South Carolina", 0.45, 0.40), 0.5) is None     # behind and priced 40%: no alert


def test_five_points_is_the_floor():
    assert priority_for(signal("Kentucky", 0.58, 0.45, away_score=22, home_score=20), 0.5) is None      # up 2
    assert priority_for(signal("Kentucky", 0.58, 0.45, away_score=23, home_score=20), 0.5) is None      # up 3, under the floor
    assert priority_for(signal("Kentucky", 0.58, 0.45, away_score=25, home_score=20), 0.5) == "normal"  # up exactly 5
    assert priority_for(signal("Kentucky", 0.58, 0.45, away_score=24, home_score=20), 0.5, min_lead=7) is None


def test_high_priority_when_espn_also_has_the_leader_as_a_clear_favorite():
    assert priority_for(signal("Kentucky", 0.65, 0.40), 0.5) == "high"
    assert priority_for(signal("Kentucky", 0.55, 0.40), 0.5) == "normal"


def test_cooldown_blocks_repeats_inside_the_window_only():
    now = datetime(2026, 10, 3, 20, 0)
    assert in_cooldown([now - timedelta(minutes=10)], now, 30)
    assert not in_cooldown([now - timedelta(minutes=45)], now, 30)
    assert not in_cooldown([], now, 30)


def test_message_says_who_is_up_and_the_gap():
    sig = signal("Kentucky", 0.62, 0.45)
    subject, body = message_for(sig, "high")
    assert subject.startswith("[Underpriced HIGH] Kentucky up 5") and "priced to lose at 45%" in subject and "ESPN 62%" in subject
    assert "pregame underdog" in body and "Kentucky 25 - South Carolina 20" in body
    assert "17 points ABOVE the market" in body                      # ESPN 62% vs market 45%
    _, agree = message_for(signal("Kentucky", 0.40, 0.45), "normal")
    assert "5 points below the market" in agree and "gap:" not in agree


def test_a_score_must_hold_across_scans_before_it_alerts():
    pending = {}
    key = ("42", "Temple")
    assert not confirmed(pending, key, True, now=100.0, hold=45)    # first sighting: only remembered
    assert not confirmed(pending, key, True, now=130.0, hold=45)    # 30s later: still too soon
    assert confirmed(pending, key, True, now=150.0, hold=45)        # 50s later and still true: confirmed


def test_a_reversed_score_resets_the_clock():
    pending = {}
    key = ("42", "Temple")
    confirmed(pending, key, True, now=100.0, hold=45)
    assert not confirmed(pending, key, False, now=130.0, hold=45)   # the touchdown was called back
    assert key not in pending
    assert not confirmed(pending, key, True, now=140.0, hold=45)    # starts over


def test_verdict_keeps_retracts_or_expires():
    assert verdict(margin=6, state="in", min_lead=3) == "keep"
    assert verdict(margin=0, state="in", min_lead=3) == "retracted"     # Temple: 9-3 became 3-3, game still on
    assert verdict(margin=-4, state="in", min_lead=3) == "retracted"
    assert verdict(margin=0, state="post", min_lead=3) == "expired"      # game over: not a false alert
    assert verdict(margin=1, state="in", min_lead=3) == "retracted"


def test_standing_finds_the_alerted_team_and_its_margin():
    boards = [{"away": {"name": "Temple Owls", "tokens": {"temple", "owls", "temple owls"}, "score": 3},
               "home": {"name": "South Florida Bulls", "tokens": {"south florida", "bulls", "south florida bulls"}, "score": 3},
               "state": "in", "detail": "13:05 - 2nd", "start": None}]
    st = standing("Temple 9 - South Florida 3", "Temple", boards)
    assert st["margin"] == 0 and st["state"] == "in"
    assert standing("Duke 3 - Wake Forest 0", "Duke", boards) is None


def test_a_normal_alert_is_labeled_underpriced():
    subject, _ = message_for(signal("Kentucky", 0.55, 0.40), "normal")
    assert subject.startswith("[Underpriced] Kentucky up 5")


from src.backend.sports.cfb import first_score_event


def ranked_game(away_rank, home_rank, detail="12:00 - 1st", away_score=0, home_score=7):
    away = TeamState("Missouri", "MIZ", away_score, away_rank, 3, 1)
    home = TeamState("Florida", "FLA", home_score, home_rank, 4, 0)
    return LiveGame(event_id="9", start=None, detail=detail, home=home, away=away)


def summary_first(team):
    return {"scoringPlays": [{"team": {"displayName": team}, "period": {"number": 1}, "clock": {"displayValue": "9:12"}, "text": "TD run"},
                              {"team": {"displayName": "Other"}, "period": {"number": 1}, "clock": {"displayValue": "3:00"}}]}


def test_unranked_scoring_first_on_a_ranked_team_triggers():
    g = ranked_game(away_rank=8, home_rank=None)                       # Missouri #8 away, Florida unranked
    ev = first_score_event(g, summary_first("Florida Gators"), {"Missouri": 0.62, "Florida": 0.38}, 0.40, "cfb-x")
    assert ev and ev.ranked.name == "Missouri" and ev.scorer.name == "Florida"
    assert ev.ranked_price == 0.62 and abs(ev.espn_win_prob - 0.60) < 1e-9


def test_a_ranked_team_scoring_first_on_another_ranked_team_does_not():
    g = ranked_game(away_rank=8, home_rank=14)
    assert first_score_event(g, summary_first("Florida Gators"), {}, None, "x") is None


def test_the_ranked_team_scoring_first_does_not():
    g = ranked_game(away_rank=8, home_rank=None)
    assert first_score_event(g, summary_first("Missouri Tigers"), {}, None, "x") is None


def test_it_must_still_be_the_first_half_and_a_scoring_play_must_exist():
    assert first_score_event(ranked_game(8, None, detail="9:00 - 3rd"), summary_first("Florida Gators"), {}, None, "x") is None
    assert first_score_event(ranked_game(8, None), {"scoringPlays": []}, {}, None, "x") is None
    assert first_score_event(ranked_game(30, None), summary_first("Florida Gators"), {}, None, "x") is None  # rank 30 is not top 25


def test_trailing_longshot_in_college_football():
    down5 = signal("Kentucky", 0.25, 0.12, away_score=15, home_score=20)
    assert priority_for(down5, 0.5) == "normal"                                                         # down 5, priced 12%
    assert priority_for(signal("Kentucky", 0.35, 0.35, away_score=15, home_score=20), 0.5) is None      # 35% is not under 30%
    assert priority_for(signal("Kentucky", 0.15, 0.10, away_score=10, home_score=20), 0.5) is None      # down 10: not one score
    assert priority_for(signal("Kentucky", 0.15, 0.10, away_score=12, home_score=20), 0.5) == "normal"  # down exactly 8
    assert verdict(-6, "in", 5, trailing=True) == "keep"
    assert verdict(-10, "in", 5, trailing=True) == "retracted"


def test_repeat_alert_when_it_gets_better():
    from datetime import datetime, timedelta
    now = datetime(2026, 10, 4, 12, 0)
    sig = signal("Kentucky", 0.6, 0.40, away_score=30, home_score=20)            # up 10, priced 40%
    assert improved((now - timedelta(minutes=10), 5, 0.40), sig, now)              # was up 5, now up 10
    assert improved((now - timedelta(minutes=10), 10, 0.50), sig, now)             # price fell 10 points
    assert not improved((now - timedelta(minutes=10), 10, 0.42), sig, now)         # nothing better
    assert not improved((now - timedelta(minutes=2), 5, 0.40), sig, now)           # too soon


def _box(home, away):
    return {"boxscore": {"teams": [
        {"homeAway": "home", "statistics": [{"name": "rushingAttempts", "displayValue": str(home[0])}, {"name": "rushingYards", "displayValue": str(home[1])}]},
        {"homeAway": "away", "statistics": [{"name": "rushingAttempts", "displayValue": str(away[0])}, {"name": "rushingYards", "displayValue": str(away[1])}]},
    ]}}


def test_rush_edge_needs_exactly_one_team_at_five_a_carry():
    from src.backend.sports.cfb import rush_edge
    g = game(17, 13)
    prices = {"Kentucky": 0.4, "South Carolina": 0.6}
    ev = rush_edge(g, _box((30, 182), (34, 113)), prices, 0.5, "slug")      # home 6.1, away 3.3
    assert ev and ev.team.name == g.home.name and round(ev.ypc, 1) == 6.1
    assert rush_edge(g, _box((30, 182), (30, 160)), prices, 0.5, "slug") is None   # both over 5
    assert rush_edge(g, _box((10, 80), (34, 113)), prices, 0.5, "slug") is None    # 10 carries: too few
    assert rush_edge(g, _box((30, 120), (34, 113)), prices, 0.5, "slug") is None   # nobody at 5


def test_no_longshot_alert_when_the_leader_can_run_out_the_clock():
    sig = signal("Kentucky", 0.15, 0.10, away_score=18, home_score=20)       # down 2, priced 10%
    sig.game.period, sig.game.seconds_left = 4, 67
    sig.game.possession = "South Carolina"
    assert priority_for(sig, 0.5) == "normal"                                 # over a minute left: still alive
    sig.game.seconds_left = 40
    assert priority_for(sig, 0.5) is None                                     # under a minute, other team has the ball
    sig.game.possession = "Kentucky"
    assert priority_for(sig, 0.5) == "normal"                                 # they have the ball: alert


def test_getting_the_ball_back_repeats_the_alert():
    from datetime import datetime, timedelta
    from src.backend.sports.alerts import got_the_ball
    now = datetime(2026, 10, 4, 12, 0)
    sig = signal("Kentucky", 0.15, 0.10, away_score=18, home_score=20)
    key = ("cfb:42", "Kentucky")
    sig.game.possession = "South Carolina"
    assert not got_the_ball(key, sig)
    sig.game.possession = "Kentucky"
    ball = got_the_ball(key, sig)
    assert ball and improved((now - timedelta(minutes=2), -2, 0.10), sig, now, ball)
    assert not improved((now - timedelta(minutes=2), -2, 0.10), sig, now, False)


def test_defense_baseline_from_box_scores():
    from src.backend.sports.defense_baseline import rush_allowed_in_game, season_ypc_allowed
    summary = {"boxscore": {"teams": [
        {"team": {"id": "1"}, "statistics": [{"name": "rushingAttempts", "displayValue": "30"}, {"name": "rushingYards", "displayValue": "150"}]},
        {"team": {"id": "2"}, "statistics": [{"name": "rushingAttempts", "displayValue": "40"}, {"name": "rushingYards", "displayValue": "120"}]},
    ]}}
    assert rush_allowed_in_game(summary, "1") == (40, 120.0)      # team 1 allowed what team 2 ran for
    assert rush_allowed_in_game(summary, "2") == (30, 150.0)
    assert season_ypc_allowed([(40, 120.0), (30, 60.0)]) == 180 / 70
    assert season_ypc_allowed([]) is None
