from src.backend.sports.registry import SPORTS, active_sports, in_scope, league_of


def test_active_sports_are_mlb_cfb_nfl_and_basketball_is_a_placeholder():
    assert [s.key for s in active_sports()] == ["mlb", "cfb", "nfl", "atp", "wta", "itfme", "itfwo"]
    status = {s.key: s.status for s in SPORTS}
    assert status["nba"] == "offseason" and status["cbb"] == "offseason"


def test_league_of_and_scope_from_slug():
    assert league_of("aec-cfb-mich-minnst-2026-10-03") == "cfb"
    assert league_of("nope") == ""
    assert in_scope("aec-nba-lal-bos-2026-11-01")  # placeholder is still in scope
    assert in_scope("aec-cbb-duke-unc-2026-11-10")
    assert in_scope("aec-atp-sinner-alcaraz-2026-10-04")
    assert not in_scope("aec-mls-mia-atl-2026-09-05")
    assert not in_scope("caoc-33afccf3b7802aa5")  # combos carry no league in the slug


def test_is_sports_market_keeps_our_leagues_and_drops_the_rest():
    from src.backend.sports.registry import is_sports_market

    for slug in ("cfb-fl-missr-2026-10-03", "mlb-atl-lad-2026-10-03", "nfl-phi-lar-2026-10-04", "atp-sinner-alcaraz-2026-10-05",
                 "wta-park-montgom-2026-09-20", "nba-lal-bos-2026-11-01", "cbb-duke-unc-2026-11-10", "itfme-a-b-2026-10-04"):
        assert is_sports_market(slug), slug
    for slug in ("will-the-fed-increase-interest-rates", "dota2-lgd-aur1-2026-10-03", "lol-sly-t1-2026-10-03",
                 "unl-tur-esp-2026-10-03", "epl-ars-che-2026-10-04", "nhl-bos-nyr-2026-10-04", "us-x-iran", ""):
        assert not is_sports_market(slug), slug
