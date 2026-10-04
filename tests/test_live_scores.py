from src.backend.sports.live_scores import describe, line_from_slug, match_game, norm, team_tokens


def game(away, away_nick, away_score, home, home_nick, home_score, state="in", detail="3rd 0:40"):
    return {"away": {"name": away, "tokens": team_tokens(away.split()[0], away_nick, away), "score": away_score},
            "home": {"name": home, "tokens": team_tokens(home.split()[0], home_nick, home), "score": home_score},
            "state": state, "detail": detail}


GAMES = [game("Kentucky Wildcats", "Wildcats", 24, "South Carolina Gamecocks", "Gamecocks", 20),
         game("Atlanta Braves", "Braves", 3, "Los Angeles Dodgers", "Dodgers", 5, detail="Top 9th")]


def test_match_by_names_in_the_title_and_playoff_style_titles():
    assert match_game("Kentucky vs. South Carolina", GAMES)["away"]["score"] == 24
    assert match_game("Game 1: ATL Braves vs. LA Dodgers", GAMES)["home"]["name"] == "Los Angeles Dodgers"
    assert match_game("Duke vs. Wake Forest", GAMES) is None


def test_pick_is_matched_by_nickname_and_marked_leading_or_trailing():
    g = match_game("Kentucky vs. South Carolina", GAMES)
    live = describe({"outcome": "Wildcats"}, g)
    assert live["status"] == "leading" and live["margin"] == 4 and live["pick"] == "Kentucky Wildcats"
    assert describe({"outcome": "Gamecocks"}, g)["status"] == "trailing"


def test_over_leg_reports_total_and_runs_needed():
    g = match_game("Game 1: ATL Braves vs. LA Dodgers", GAMES)
    live = describe({"outcome": "Over", "slug": "tsc-mlb-atl-lad-2026-10-03-8pt5"}, g)
    assert live["total"] == 8 and live["line"] == 8.5 and live["needs"] == 1


def test_line_from_slug_and_norm():
    assert line_from_slug("tsc-mlb-phi-atl-2026-09-30-7pt5") == 7.5
    assert line_from_slug("aec-mlb-a-b-2026-10-03") is None
    assert norm("St. Louis-Cardinals") == "st louis cardinals"


def test_series_game_is_chosen_by_start_time():
    g1 = {**game("Atlanta Braves", "Braves", 3, "Los Angeles Dodgers", "Dodgers", 5, "post", "Final"), "start": "2026-10-03T22:00:00Z"}
    g2 = {**game("Atlanta Braves", "Braves", 0, "Los Angeles Dodgers", "Dodgers", 0, "pre", "Scheduled"), "start": "2026-10-05T00:00:00Z"}
    title = "Game 1: ATL Braves vs. LA Dodgers"
    assert match_game(title, [g2, g1], start="2026-10-03T22:05:00Z")["state"] == "post"
    assert match_game(title, [g1, g2], start="2026-10-05T00:00:00Z")["state"] == "pre"
    assert match_game(title, [g1, g2])["state"] == "pre"  # no start time: upcoming before finished
