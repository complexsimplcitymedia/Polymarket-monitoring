import pytest

from src.backend.sports.mlb_context import Game, day_before, parse_games, team_form


def g(day, away, home, ar, hr):
    return Game(day, away, home, ar, hr)


GAMES = [
    g("2026-09-01", "Padres", "Rockies", 5, 2),   # Padres win
    g("2026-09-02", "Padres", "Rockies", 1, 3),   # Padres lose
    g("2026-09-03", "Dodgers", "Padres", 0, 4),   # Padres win at home
    g("2026-09-04", "Dodgers", "Padres", 6, 2),   # Padres lose
    g("2026-09-05", "Cubs", "Padres", 2, 8),      # Padres win
]


def test_form_uses_only_games_before_the_date_and_last_n():
    f = team_form(GAMES, "Padres", before="2026-09-05", n=10)
    assert (f.wins, f.losses, f.games) == (2, 2, 4)  # the 5th is the game itself, excluded
    last2 = team_form(GAMES, "Padres", before="2026-09-05", n=2)
    assert (last2.wins, last2.losses) == (1, 1)  # Sept 3 win, Sept 4 loss


def test_form_run_rates_count_the_right_side_of_each_game():
    f = team_form(GAMES, "Padres", before="2026-09-05", n=10)
    assert f.runs_for == pytest.approx((5 + 1 + 4 + 2) / 4)
    assert f.runs_against == pytest.approx((2 + 3 + 0 + 6) / 4)


def test_form_is_none_when_no_games_precede_the_date():
    assert team_form(GAMES, "Padres", before="2026-09-01", n=10) is None
    assert team_form(GAMES, "Yankees", before="2026-09-09", n=10) is None


def test_parse_games_keeps_only_finished_games_with_scores():
    payload = {"dates": [{"games": [
        {"officialDate": "2026-09-01", "status": {"abstractGameState": "Final"},
         "teams": {"away": {"team": {"name": "A"}, "score": 3}, "home": {"team": {"name": "B"}, "score": 4}}},
        {"officialDate": "2026-09-01", "status": {"abstractGameState": "Live"},
         "teams": {"away": {"team": {"name": "C"}, "score": 1}, "home": {"team": {"name": "D"}, "score": 0}}},
    ]}]}
    games = parse_games(payload)
    assert len(games) == 1 and games[0].winner == "B"


def test_day_before():
    assert day_before("2026-09-01") == "2026-08-31"
