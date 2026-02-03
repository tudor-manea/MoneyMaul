"""Tests for data models."""

from datetime import date

import pytest

from src.models import (
    Country,
    Match,
    Player,
    PlayerMatchStats,
    Position,
    SelectionStatus,
    Team,
    MAX_BUDGET,
    MAX_PER_COUNTRY,
)


class TestPlayer:
    """Tests for Player model."""

    def test_create_player(self) -> None:
        """Test basic player creation."""
        player = Player(
            id="p1",
            name="Antoine Dupont",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=15.0,
        )
        assert player.name == "Antoine Dupont"
        assert player.country == Country.FRANCE
        assert player.position == Position.BACK
        assert player.star_value == 15.0
        assert player.ownership_pct is None

    def test_player_with_ownership(self) -> None:
        """Test player with ownership percentage."""
        player = Player(
            id="p1",
            name="Maro Itoje",
            country=Country.ENGLAND,
            position=Position.FORWARD,
            star_value=12.5,
            ownership_pct=45.2,
        )
        assert player.ownership_pct == 45.2

    def test_player_is_forward(self) -> None:
        """Test forward position check."""
        player = Player(
            id="p1",
            name="Tadhg Furlong",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=11.0,
        )
        assert player.is_forward is True
        assert player.is_back is False

    def test_player_is_back(self) -> None:
        """Test back position check."""
        player = Player(
            id="p1",
            name="Finn Russell",
            country=Country.SCOTLAND,
            position=Position.BACK,
            star_value=13.0,
        )
        assert player.is_forward is False
        assert player.is_back is True

    def test_negative_star_value_raises(self) -> None:
        """Test that negative star value raises error."""
        with pytest.raises(ValueError, match="star_value cannot be negative"):
            Player(
                id="p1",
                name="Test Player",
                country=Country.WALES,
                position=Position.BACK,
                star_value=-1.0,
            )

    def test_excessive_star_value_raises(self) -> None:
        """Test that star value over budget raises error."""
        with pytest.raises(ValueError, match="star_value cannot exceed"):
            Player(
                id="p1",
                name="Test Player",
                country=Country.ITALY,
                position=Position.FORWARD,
                star_value=201.0,
            )

    def test_invalid_ownership_raises(self) -> None:
        """Test that invalid ownership percentage raises error."""
        with pytest.raises(ValueError, match="ownership_pct must be between"):
            Player(
                id="p1",
                name="Test Player",
                country=Country.FRANCE,
                position=Position.BACK,
                star_value=10.0,
                ownership_pct=150.0,
            )


class TestPlayerMatchStats:
    """Tests for PlayerMatchStats model."""

    def test_create_stats(self) -> None:
        """Test basic stats creation."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.STARTER,
            tries=2,
            tackles=5,
        )
        assert stats.player_id == "p1"
        assert stats.tries == 2
        assert stats.tackles == 5
        assert stats.played is True
        assert stats.was_substitute is False

    def test_substitute_status(self) -> None:
        """Test substitute detection."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.SUBSTITUTE,
        )
        assert stats.played is True
        assert stats.was_substitute is True

    def test_not_selected(self) -> None:
        """Test not selected status."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.NOT_SELECTED,
        )
        assert stats.played is False
        assert stats.was_substitute is False

    def test_default_values(self) -> None:
        """Test all stats default to zero."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1")
        assert stats.tries == 0
        assert stats.try_assists == 0
        assert stats.tackles == 0
        assert stats.player_of_match is False

    def test_negative_stat_raises(self) -> None:
        """Test that negative stats raise error."""
        with pytest.raises(ValueError, match="tries cannot be negative"):
            PlayerMatchStats(player_id="p1", match_id="m1", tries=-1)


class TestMatch:
    """Tests for Match model."""

    def test_create_match(self) -> None:
        """Test basic match creation."""
        match = Match(
            id="m1",
            home_team="France",
            away_team="Ireland",
            match_date=date(2025, 2, 1),
            gameweek=1,
        )
        assert match.home_team == "France"
        assert match.away_team == "Ireland"
        assert match.is_completed is False

    def test_completed_match(self) -> None:
        """Test match with scores."""
        match = Match(
            id="m1",
            home_team="England",
            away_team="Scotland",
            match_date=date(2025, 2, 1),
            gameweek=1,
            home_score=23,
            away_score=17,
        )
        assert match.is_completed is True

    def test_invalid_gameweek_raises(self) -> None:
        """Test invalid gameweek raises error."""
        with pytest.raises(ValueError, match="gameweek must be between"):
            Match(
                id="m1",
                home_team="Wales",
                away_team="Italy",
                match_date=date(2025, 2, 1),
                gameweek=6,
            )

    def test_negative_score_raises(self) -> None:
        """Test negative score raises error."""
        with pytest.raises(ValueError, match="home_score cannot be negative"):
            Match(
                id="m1",
                home_team="Wales",
                away_team="Italy",
                match_date=date(2025, 2, 1),
                gameweek=1,
                home_score=-5,
            )


class TestTeam:
    """Tests for Team model."""

    @pytest.fixture
    def sample_players(self) -> list[Player]:
        """Create sample players for testing."""
        return [
            Player(id=f"p{i}", name=f"Player {i}", country=Country.FRANCE, position=Position.BACK, star_value=10.0)
            for i in range(15)
        ]

    def test_empty_team(self) -> None:
        """Test empty team properties."""
        team = Team()
        assert team.squad_size == 0
        assert team.total_value == 0
        assert team.budget_remaining == MAX_BUDGET
        assert team.is_valid is False

    def test_add_player(self, sample_players: list[Player]) -> None:
        """Test adding players to team."""
        team = Team()
        team.add_player(sample_players[0])
        assert team.squad_size == 1
        assert team.get_player("p0") == sample_players[0]

    def test_add_duplicate_player_raises(self, sample_players: list[Player]) -> None:
        """Test adding duplicate player raises error."""
        team = Team()
        team.add_player(sample_players[0])
        with pytest.raises(ValueError, match="already in squad"):
            team.add_player(sample_players[0])

    def test_remove_player(self, sample_players: list[Player]) -> None:
        """Test removing player from team."""
        team = Team()
        team.add_player(sample_players[0])
        team.remove_player("p0")
        assert team.squad_size == 0

    def test_remove_nonexistent_player_raises(self) -> None:
        """Test removing nonexistent player raises error."""
        team = Team()
        with pytest.raises(ValueError, match="not in squad"):
            team.remove_player("p99")

    def test_set_captain(self, sample_players: list[Player]) -> None:
        """Test setting captain."""
        team = Team()
        team.add_player(sample_players[0])
        team.set_captain("p0")
        assert team.captain_id == "p0"
        assert team.captain == sample_players[0]

    def test_set_captain_not_in_squad_raises(self) -> None:
        """Test setting captain not in squad raises error."""
        team = Team()
        with pytest.raises(ValueError, match="not in squad"):
            team.set_captain("p99")

    def test_set_supersub(self, sample_players: list[Player]) -> None:
        """Test setting supersub."""
        team = Team()
        team.add_player(sample_players[0])
        team.add_player(sample_players[1])
        team.set_captain("p0")
        team.set_supersub("p1")
        assert team.supersub_id == "p1"
        assert team.supersub == sample_players[1]

    def test_supersub_cannot_be_captain(self, sample_players: list[Player]) -> None:
        """Test supersub cannot be captain."""
        team = Team()
        team.add_player(sample_players[0])
        team.set_captain("p0")
        with pytest.raises(ValueError, match="Captain cannot also be supersub"):
            team.set_supersub("p0")

    def test_captain_cannot_be_supersub(self, sample_players: list[Player]) -> None:
        """Test captain cannot be set to existing supersub."""
        team = Team()
        team.add_player(sample_players[0])
        team.add_player(sample_players[1])
        team.set_supersub("p0")
        with pytest.raises(ValueError, match="Supersub cannot also be captain"):
            team.set_captain("p0")

    def test_remove_player_clears_captain(self, sample_players: list[Player]) -> None:
        """Test removing captain clears captain_id."""
        team = Team()
        team.add_player(sample_players[0])
        team.set_captain("p0")
        team.remove_player("p0")
        assert team.captain_id is None

    def test_valid_team(self) -> None:
        """Test a valid team passes validation."""
        # Create 15 players spread across countries
        players = []
        countries = list(Country)
        for i in range(15):
            country = countries[i % len(countries)]
            players.append(
                Player(
                    id=f"p{i}",
                    name=f"Player {i}",
                    country=country,
                    position=Position.BACK if i % 2 == 0 else Position.FORWARD,
                    star_value=10.0,
                )
            )
        team = Team(players=players)
        assert team.is_valid is True
        assert team.is_complete is True

    def test_over_budget_validation(self) -> None:
        """Test over budget validation error."""
        players = [
            Player(id=f"p{i}", name=f"Player {i}", country=Country.FRANCE, position=Position.BACK, star_value=15.0)
            for i in range(15)
        ]
        team = Team(players=players)  # 15 * 15 = 225 stars
        errors = team.validate()
        error_codes = [e.code for e in errors]
        assert "OVER_BUDGET" in error_codes

    def test_country_limit_validation(self) -> None:
        """Test country limit validation error."""
        players = [
            Player(id=f"p{i}", name=f"Player {i}", country=Country.IRELAND, position=Position.BACK, star_value=10.0)
            for i in range(15)
        ]
        team = Team(players=players)  # All from same country
        errors = team.validate()
        error_codes = [e.code for e in errors]
        assert "COUNTRY_LIMIT" in error_codes

    def test_under_min_squad_validation(self) -> None:
        """Test under minimum squad validation error."""
        players = [
            Player(id=f"p{i}", name=f"Player {i}", country=Country.ENGLAND, position=Position.BACK, star_value=10.0)
            for i in range(5)
        ]
        team = Team(players=players)
        errors = team.validate()
        error_codes = [e.code for e in errors]
        assert "UNDER_MIN_SQUAD" in error_codes

    def test_country_counts(self) -> None:
        """Test country counts property."""
        players = [
            Player(id="p1", name="Player 1", country=Country.FRANCE, position=Position.BACK, star_value=10.0),
            Player(id="p2", name="Player 2", country=Country.FRANCE, position=Position.FORWARD, star_value=10.0),
            Player(id="p3", name="Player 3", country=Country.IRELAND, position=Position.BACK, star_value=10.0),
        ]
        team = Team(players=players)
        counts = team.country_counts
        assert counts[Country.FRANCE] == 2
        assert counts[Country.IRELAND] == 1
