"""Tests for the Streamlit app module."""

import pytest

from src.models import Country, Player, Position, Team
from src.app.pages.team_builder import (
    _get_extended_players,
    _filter_players,
)


class TestExtendedPlayers:
    """Tests for extended player data."""

    def test_returns_list(self) -> None:
        """Should return a list of players."""
        players = _get_extended_players()
        assert isinstance(players, list)
        assert len(players) > 0

    def test_all_players_valid(self) -> None:
        """All players should be valid Player objects."""
        players = _get_extended_players()
        for player in players:
            assert isinstance(player, Player)
            assert isinstance(player.country, Country)
            assert isinstance(player.position, Position)
            assert player.star_value > 0

    def test_has_players_from_all_countries(self) -> None:
        """Should have players from all six nations."""
        players = _get_extended_players()
        countries = {p.country for p in players}
        assert countries == set(Country)

    def test_has_forwards_and_backs(self) -> None:
        """Should have both forwards and backs."""
        players = _get_extended_players()
        positions = {p.position for p in players}
        assert Position.FORWARD in positions
        assert Position.BACK in positions

    def test_unique_player_ids(self) -> None:
        """All player IDs should be unique."""
        players = _get_extended_players()
        ids = [p.id for p in players]
        assert len(ids) == len(set(ids))

    def test_enough_players_for_full_squad(self) -> None:
        """Should have enough players to build a full 15-16 player squad."""
        players = _get_extended_players()
        # Need at least 15 players total
        assert len(players) >= 15

    def test_can_afford_15_players(self) -> None:
        """Should be able to afford at least 15 players within budget."""
        players = _get_extended_players()
        # Sort by value and take cheapest 15
        sorted_players = sorted(players, key=lambda p: p.star_value)
        cheapest_15_value = sum(p.star_value for p in sorted_players[:15])
        # Should be under 200 budget
        assert cheapest_15_value <= 200


class TestFilterPlayers:
    """Tests for player filtering."""

    @pytest.fixture
    def sample_players(self) -> list[Player]:
        """Create sample players for testing filters."""
        return [
            Player(
                id="p1",
                name="Player 1",
                country=Country.ENGLAND,
                position=Position.BACK,
                star_value=10.0,
            ),
            Player(
                id="p2",
                name="Player 2",
                country=Country.FRANCE,
                position=Position.FORWARD,
                star_value=12.0,
            ),
            Player(
                id="p3",
                name="Player 3",
                country=Country.ENGLAND,
                position=Position.FORWARD,
                star_value=15.0,
            ),
            Player(
                id="p4",
                name="Player 4",
                country=Country.IRELAND,
                position=Position.BACK,
                star_value=8.0,
            ),
        ]

    def test_filter_all_returns_all(self, sample_players: list[Player]) -> None:
        """'All' filters should return all players."""
        result = _filter_players(sample_players, "All", "All", 20.0)
        assert len(result) == 4

    def test_filter_by_country(self, sample_players: list[Player]) -> None:
        """Should filter by country."""
        result = _filter_players(sample_players, "England", "All", 20.0)
        assert len(result) == 2
        assert all(p.country == Country.ENGLAND for p in result)

    def test_filter_by_position_forward(self, sample_players: list[Player]) -> None:
        """Should filter by forward position."""
        result = _filter_players(sample_players, "All", "Forward", 20.0)
        assert len(result) == 2
        assert all(p.position == Position.FORWARD for p in result)

    def test_filter_by_position_back(self, sample_players: list[Player]) -> None:
        """Should filter by back position."""
        result = _filter_players(sample_players, "All", "Back", 20.0)
        assert len(result) == 2
        assert all(p.position == Position.BACK for p in result)

    def test_filter_by_max_price(self, sample_players: list[Player]) -> None:
        """Should filter by maximum price."""
        result = _filter_players(sample_players, "All", "All", 11.0)
        assert len(result) == 2
        assert all(p.star_value <= 11.0 for p in result)

    def test_filter_combined(self, sample_players: list[Player]) -> None:
        """Should combine all filters."""
        result = _filter_players(sample_players, "England", "Forward", 20.0)
        assert len(result) == 1
        assert result[0].id == "p3"

    def test_returns_sorted_by_value_descending(self, sample_players: list[Player]) -> None:
        """Should return players sorted by star value descending."""
        result = _filter_players(sample_players, "All", "All", 20.0)
        values = [p.star_value for p in result]
        assert values == sorted(values, reverse=True)

    def test_empty_result_when_no_matches(self, sample_players: list[Player]) -> None:
        """Should return empty list when no players match."""
        result = _filter_players(sample_players, "Wales", "All", 20.0)
        assert result == []


class TestAppImports:
    """Tests for app module imports."""

    def test_main_import(self) -> None:
        """Should be able to import main module."""
        pytest.importorskip("streamlit")
        from src.app import main
        assert callable(main)

    def test_team_builder_import(self) -> None:
        """Should be able to import team builder page."""
        pytest.importorskip("streamlit")
        from src.app.pages import team_builder
        assert hasattr(team_builder, "render")

    def test_components_import(self) -> None:
        """Should be able to import components."""
        pytest.importorskip("streamlit")
        from src.app.components import (
            render_player_table,
            render_team_status,
            render_validation,
        )
        assert callable(render_player_table)
        assert callable(render_team_status)
        assert callable(render_validation)
