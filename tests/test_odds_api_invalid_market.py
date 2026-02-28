import pytest


def test_extract_invalid_markets_from_message():
    from src.sources import odds_api

    msg = 'Odds API request failed: 422 {"error_code":"INVALID_MARKET","message":"Invalid markets: player_aces,player_sets_won"}'
    assert odds_api._extract_invalid_markets(msg) == ["player_aces", "player_sets_won"]


def test_extract_invalid_markets_from_plain_text():
    from src.sources import odds_api

    msg = "Invalid markets: player_games_won,player_double_faults"
    assert odds_api._extract_invalid_markets(msg) == ["player_games_won", "player_double_faults"]


def test_fetch_player_props_invalid_markets_returns_empty(monkeypatch):
    from src.sources import odds_api

    class FakeClient:
        def __init__(self):
            self.calls = 0

        def get_events(self, *, sport_key: str):
            return ([{"id": "ev1"}], odds_api.OddsApiQuota(remaining=100, used=0, last_cost=1))

        def get_event_odds(
            self,
            *,
            sport_key: str,
            event_id: str,
            regions: str,
            markets: str,
            odds_format: str = "american",
            date_format: str = "iso",
            bookmakers=None,
            include_multipliers: bool = False,
        ):
            self.calls += 1
            raise odds_api.OddsApiError(
                '{"error_code":"INVALID_MARKET","message":"Invalid markets: player_aces,player_sets_won"}'
            )

        def get_event_markets(self, *, sport_key: str, event_id: str, regions: str, date_format: str = "iso", bookmakers=None):
            # Only featured markets exist; should lead to empty intersection and a skipped event.
            return (
                {
                    "id": event_id,
                    "bookmakers": [
                        {"key": "underdog", "markets": [{"key": "h2h"}, {"key": "totals"}]}
                    ],
                },
                odds_api.OddsApiQuota(remaining=100, used=0, last_cost=1),
            )

    monkeypatch.setattr(odds_api.OddsApiClient, "from_env", classmethod(lambda cls: FakeClient()))

    props, meta = odds_api.oddsapi_fetch_player_props(
        sport="TENNIS",
        sport_key="tennis_wta_example",
        regions="us_dfs",
        markets=("player_aces", "player_sets_won"),
        bookmakers=("underdog",),
        max_events=1,
    )

    assert props == []
    assert meta.get("invalid_markets_dropped") is not None


def test_fetch_player_props_drops_invalid_and_retries(monkeypatch):
    from src.sources import odds_api

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_events(self, *, sport_key: str):
            return ([{"id": "ev1"}], odds_api.OddsApiQuota(remaining=100, used=0, last_cost=1))

        def get_event_odds(
            self,
            *,
            sport_key: str,
            event_id: str,
            regions: str,
            markets: str,
            odds_format: str = "american",
            date_format: str = "iso",
            bookmakers=None,
            include_multipliers: bool = False,
        ):
            self.calls.append(markets)
            if "bad_market" in markets:
                raise odds_api.OddsApiError(
                    '{"error_code":"INVALID_MARKET","message":"Invalid markets: bad_market"}'
                )
            return (
                {"id": event_id, "bookmakers": []},
                odds_api.OddsApiQuota(remaining=100, used=0, last_cost=1),
            )

    monkeypatch.setattr(odds_api.OddsApiClient, "from_env", classmethod(lambda cls: FakeClient()))

    props, meta = odds_api.oddsapi_fetch_player_props(
        sport="NBA",
        sport_key="basketball_nba",
        regions="us_dfs",
        markets=("bad_market", "player_points"),
        bookmakers=("underdog",),
        max_events=1,
    )

    # No props in response (empty bookmakers), but function should succeed.
    assert props == []
    assert meta.get("invalid_markets_dropped") == ["bad_market"]
