"""Tests for team validation utilities."""

import pytest

from src.analysis.validator import (
    ValidationResult,
    can_add_player,
    can_make_transfer,
    can_remove_player,
    find_affordable_transfers,
    get_available_slots_for_country,
    get_max_player_value,
    get_squad_slots_remaining,
    get_transfer_budget,
    validate_team,
)
from src.models import Country, Player, Position, Team, MAX_BUDGET


def make_player(
    id: str,
    country: Country = Country.FRANCE,
    position: Position = Position.BACK,
    star_value: float = 10.0,
) -> Player:
    """Helper to create test players."""
    return Player(
        id=id,
        name=f"Player {id}",
        country=country,
        position=position,
        star_value=star_value,
    )


def make_valid_team() -> Team:
    """Create a valid 15-player team spread across countries."""
    countries = list(Country)
    players = [
        make_player(
            id=f"p{i}",
            country=countries[i % len(countries)],
            star_value=10.0,
        )
        for i in range(15)
    ]
    team = Team(players=players)
    team.set_captain("p0")
    team.set_supersub("p1")
    return team


class TestValidateTeam:
    """Tests for validate_team function."""

    def test_valid_team(self) -> None:
        """Test validation of a complete valid team."""
        team = make_valid_team()
        result = validate_team(team)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_incomplete_team_warning(self) -> None:
        """Test warning for incomplete squad."""
        players = [make_player(f"p{i}") for i in range(10)]
        team = Team(players=players)

        result = validate_team(team)

        assert result.is_valid is False  # Under min squad
        assert any("Incomplete squad" in w for w in result.warnings)
        assert any("points will be halved" in w for w in result.warnings)

    def test_missing_captain_warning(self) -> None:
        """Test warning when no captain selected."""
        team = make_valid_team()
        team.captain_id = None

        result = validate_team(team)

        assert any("No captain selected" in w for w in result.warnings)

    def test_missing_supersub_warning(self) -> None:
        """Test warning when no supersub selected."""
        team = make_valid_team()
        team.supersub_id = None

        result = validate_team(team)

        assert any("No supersub selected" in w for w in result.warnings)

    def test_empty_team_no_role_warnings(self) -> None:
        """Test empty team doesn't warn about missing roles."""
        team = Team()
        result = validate_team(team)

        assert not any("captain" in w.lower() for w in result.warnings)
        assert not any("supersub" in w.lower() for w in result.warnings)


class TestCanAddPlayer:
    """Tests for can_add_player function."""

    def test_add_to_empty_team(self) -> None:
        """Test adding player to empty team."""
        team = Team()
        player = make_player("p1")

        result = can_add_player(team, player)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_add_duplicate_player(self) -> None:
        """Test adding player already in squad."""
        player = make_player("p1")
        team = Team(players=[player])

        result = can_add_player(team, player)

        assert result.is_valid is False
        assert any(e.code == "DUPLICATE_PLAYER" for e in result.errors)

    def test_add_to_full_squad(self) -> None:
        """Test adding player to full squad."""
        countries = list(Country)
        players = [
            make_player(f"p{i}", country=countries[i % len(countries)])
            for i in range(16)
        ]
        team = Team(players=players)
        new_player = make_player("p99")

        result = can_add_player(team, new_player)

        assert result.is_valid is False
        assert any(e.code == "SQUAD_FULL" for e in result.errors)

    def test_add_exceeds_budget(self) -> None:
        """Test adding player that exceeds budget."""
        players = [make_player(f"p{i}", star_value=13.0) for i in range(15)]
        team = Team(players=players)  # 195 stars used
        expensive_player = make_player("p99", star_value=10.0)  # Would be 205

        result = can_add_player(team, expensive_player)

        assert result.is_valid is False
        assert any(e.code == "INSUFFICIENT_BUDGET" for e in result.errors)

    def test_add_exceeds_country_limit(self) -> None:
        """Test adding player when country limit reached."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        team = Team(players=players)
        another_french = make_player("p99", country=Country.FRANCE)

        result = can_add_player(team, another_french)

        assert result.is_valid is False
        assert any(e.code == "COUNTRY_LIMIT_REACHED" for e in result.errors)

    def test_add_different_country_ok(self) -> None:
        """Test adding player from different country is ok."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        team = Team(players=players)
        irish_player = make_player("p99", country=Country.IRELAND)

        result = can_add_player(team, irish_player)

        assert result.is_valid is True


class TestCanRemovePlayer:
    """Tests for can_remove_player function."""

    def test_remove_existing_player(self) -> None:
        """Test removing an existing player."""
        team = make_valid_team()

        result = can_remove_player(team, "p5")

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_remove_nonexistent_player(self) -> None:
        """Test removing a player not in squad."""
        team = make_valid_team()

        result = can_remove_player(team, "p99")

        assert result.is_valid is False
        assert any(e.code == "PLAYER_NOT_FOUND" for e in result.errors)

    def test_remove_captain_warning(self) -> None:
        """Test warning when removing captain."""
        team = make_valid_team()

        result = can_remove_player(team, "p0")  # Captain

        assert result.is_valid is True
        assert any("captain" in w.lower() for w in result.warnings)

    def test_remove_supersub_warning(self) -> None:
        """Test warning when removing supersub."""
        team = make_valid_team()

        result = can_remove_player(team, "p1")  # Supersub

        assert result.is_valid is True
        assert any("supersub" in w.lower() for w in result.warnings)


class TestCanMakeTransfer:
    """Tests for can_make_transfer function."""

    def test_valid_transfer(self) -> None:
        """Test a valid transfer."""
        team = make_valid_team()
        new_player = make_player("p99", country=Country.FRANCE)

        result = can_make_transfer(team, "p5", new_player)

        assert result.is_valid is True

    def test_transfer_player_not_in_squad(self) -> None:
        """Test transfer with player_out not in squad."""
        team = make_valid_team()
        new_player = make_player("p99")

        result = can_make_transfer(team, "p999", new_player)

        assert result.is_valid is False
        assert any(e.code == "PLAYER_NOT_FOUND" for e in result.errors)

    def test_transfer_player_already_in_squad(self) -> None:
        """Test transfer with player_in already in squad."""
        team = make_valid_team()
        existing = team.get_player("p3")
        assert existing is not None

        result = can_make_transfer(team, "p5", existing)

        assert result.is_valid is False
        assert any(e.code == "DUPLICATE_PLAYER" for e in result.errors)

    def test_transfer_exceeds_budget(self) -> None:
        """Test transfer that exceeds budget."""
        team = make_valid_team()  # 150 stars, 50 remaining
        expensive = make_player("p99", star_value=61.0)  # 61 > 60 (50 + 10)

        result = can_make_transfer(team, "p5", expensive)  # p5 is 10 stars

        assert result.is_valid is False
        assert any(e.code == "INSUFFICIENT_BUDGET" for e in result.errors)

    def test_transfer_country_limit(self) -> None:
        """Test transfer that violates country limit."""
        # Create team with 4 French players
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        # Add some other country players
        players.extend([
            make_player(f"p{i}", country=Country.ENGLAND)
            for i in range(4, 15)
        ])
        team = Team(players=players)

        # Try to swap an English player for another French one
        new_french = make_player("p99", country=Country.FRANCE)

        result = can_make_transfer(team, "p4", new_french)  # p4 is English

        assert result.is_valid is False
        assert any(e.code == "COUNTRY_LIMIT_REACHED" for e in result.errors)

    def test_transfer_same_country_ok(self) -> None:
        """Test transfer with same country works at limit."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        players.extend([
            make_player(f"p{i}", country=Country.ENGLAND)
            for i in range(4, 15)
        ])
        team = Team(players=players)

        # Swap French for French - should work
        new_french = make_player("p99", country=Country.FRANCE)

        result = can_make_transfer(team, "p0", new_french)  # p0 is French

        assert result.is_valid is True

    def test_transfer_captain_warning(self) -> None:
        """Test warning when transferring out captain."""
        team = make_valid_team()
        new_player = make_player("p99")

        result = can_make_transfer(team, "p0", new_player)  # p0 is captain

        assert result.is_valid is True
        assert any("captain" in w.lower() for w in result.warnings)


class TestBudgetHelpers:
    """Tests for budget calculation helpers."""

    def test_get_max_player_value(self) -> None:
        """Test max player value calculation."""
        players = [make_player(f"p{i}", star_value=10.0) for i in range(10)]
        team = Team(players=players)  # 100 stars used

        assert get_max_player_value(team) == 100.0

    def test_get_transfer_budget(self) -> None:
        """Test transfer budget calculation."""
        players = [make_player(f"p{i}", star_value=10.0) for i in range(15)]
        team = Team(players=players)  # 150 stars used, 50 remaining

        player_out = team.get_player("p0")
        assert player_out is not None

        assert get_transfer_budget(team, player_out) == 60.0  # 50 + 10


class TestSlotHelpers:
    """Tests for slot calculation helpers."""

    def test_get_available_slots_for_country(self) -> None:
        """Test country slot calculation."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(3)]
        team = Team(players=players)

        assert get_available_slots_for_country(team, Country.FRANCE) == 1
        assert get_available_slots_for_country(team, Country.IRELAND) == 4

    def test_get_available_slots_at_limit(self) -> None:
        """Test country slots when at limit."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        team = Team(players=players)

        assert get_available_slots_for_country(team, Country.FRANCE) == 0

    def test_get_squad_slots_remaining(self) -> None:
        """Test squad slots remaining."""
        players = [make_player(f"p{i}") for i in range(10)]
        team = Team(players=players)

        assert get_squad_slots_remaining(team) == 6

    def test_get_squad_slots_full(self) -> None:
        """Test squad slots when full."""
        countries = list(Country)
        players = [
            make_player(f"p{i}", country=countries[i % len(countries)])
            for i in range(16)
        ]
        team = Team(players=players)

        assert get_squad_slots_remaining(team) == 0


class TestFindAffordableTransfers:
    """Tests for find_affordable_transfers function."""

    def test_find_affordable_transfers_basic(self) -> None:
        """Test finding affordable transfers."""
        players = [make_player(f"p{i}", star_value=10.0) for i in range(15)]
        team = Team(players=players)  # 150 used, 50 remaining
        player_out = team.get_player("p0")
        assert player_out is not None

        candidates = [
            make_player("c1", star_value=50.0),  # 60 budget, ok
            make_player("c2", star_value=61.0),  # Too expensive
            make_player("c3", star_value=60.0),  # Exactly at limit
        ]

        result = find_affordable_transfers(team, player_out, candidates)

        assert len(result) == 2
        assert any(p.id == "c1" for p in result)
        assert any(p.id == "c3" for p in result)

    def test_find_affordable_transfers_excludes_existing(self) -> None:
        """Test that existing players are excluded."""
        players = [make_player(f"p{i}") for i in range(15)]
        team = Team(players=players)
        player_out = team.get_player("p0")
        assert player_out is not None

        candidates = [
            make_player("c1"),
            team.get_player("p5"),  # Already in squad
        ]
        # Filter out None
        candidates = [c for c in candidates if c is not None]

        result = find_affordable_transfers(team, player_out, candidates)

        assert len(result) == 1
        assert result[0].id == "c1"

    def test_find_affordable_transfers_country_limit(self) -> None:
        """Test country limit is respected."""
        players = [make_player(f"p{i}", country=Country.FRANCE) for i in range(4)]
        players.extend([
            make_player(f"p{i}", country=Country.ENGLAND)
            for i in range(4, 15)
        ])
        team = Team(players=players)
        player_out = team.get_player("p4")  # English player
        assert player_out is not None

        candidates = [
            make_player("c1", country=Country.FRANCE),  # Would exceed limit
            make_player("c2", country=Country.ENGLAND),  # Same country, ok
            make_player("c3", country=Country.IRELAND),  # Different, under limit
        ]

        result = find_affordable_transfers(team, player_out, candidates)

        assert len(result) == 2
        assert any(p.id == "c2" for p in result)
        assert any(p.id == "c3" for p in result)
        assert not any(p.id == "c1" for p in result)
