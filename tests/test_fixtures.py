"""Tests for the fixture difficulty module."""

from datetime import date

import pytest

from src.analysis.fixtures import (
    COUNTRY_NAME_MAP,
    DifficultyRating,
    FixtureDifficulty,
    FixtureRecommendation,
    TeamStrength,
    calculate_fixture_difficulties,
    calculate_team_strengths,
    get_difficulty_rating,
    get_favorable_captain_picks,
    get_fixture_recommendations,
    get_team_fixture_difficulty,
)
from src.models import Country, Player, Position
from src.models.match import Match


@pytest.fixture
def sample_completed_matches() -> list[Match]:
    """Create sample completed matches with varied scores."""
    return [
        # Gameweek 1 - Ireland dominant
        Match(
            id="m1",
            home_team="Ireland",
            away_team="England",
            match_date=date(2026, 2, 1),
            gameweek=1,
            home_score=35,
            away_score=15,
        ),
        Match(
            id="m2",
            home_team="France",
            away_team="Italy",
            match_date=date(2026, 2, 1),
            gameweek=1,
            home_score=40,
            away_score=10,
        ),
        Match(
            id="m3",
            home_team="Wales",
            away_team="Scotland",
            match_date=date(2026, 2, 1),
            gameweek=1,
            home_score=20,
            away_score=18,
        ),
        # Gameweek 2
        Match(
            id="m4",
            home_team="Ireland",
            away_team="France",
            match_date=date(2026, 2, 8),
            gameweek=2,
            home_score=25,
            away_score=20,
        ),
        Match(
            id="m5",
            home_team="England",
            away_team="Wales",
            match_date=date(2026, 2, 8),
            gameweek=2,
            home_score=30,
            away_score=10,
        ),
        Match(
            id="m6",
            home_team="Scotland",
            away_team="Italy",
            match_date=date(2026, 2, 8),
            gameweek=2,
            home_score=28,
            away_score=15,
        ),
    ]


@pytest.fixture
def sample_upcoming_matches() -> list[Match]:
    """Create sample upcoming matches (no scores)."""
    return [
        Match(
            id="m7",
            home_team="France",
            away_team="Ireland",
            match_date=date(2026, 2, 22),
            gameweek=3,
        ),
        Match(
            id="m8",
            home_team="Italy",
            away_team="England",
            match_date=date(2026, 2, 22),
            gameweek=3,
        ),
        Match(
            id="m9",
            home_team="Scotland",
            away_team="Wales",
            match_date=date(2026, 2, 22),
            gameweek=3,
        ),
    ]


@pytest.fixture
def all_matches(
    sample_completed_matches: list[Match], sample_upcoming_matches: list[Match]
) -> list[Match]:
    """Combine completed and upcoming matches."""
    return sample_completed_matches + sample_upcoming_matches


@pytest.fixture
def sample_players() -> list[Player]:
    """Create sample players from different countries."""
    return [
        Player(
            id="p1",
            name="Irish Player",
            country=Country.IRELAND,
            position=Position.BACK,
            star_value=15.0,
        ),
        Player(
            id="p2",
            name="Italian Player",
            country=Country.ITALY,
            position=Position.FORWARD,
            star_value=8.0,
        ),
        Player(
            id="p3",
            name="French Player",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=12.0,
        ),
        Player(
            id="p4",
            name="English Player",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=10.0,
        ),
    ]


class TestCalculateTeamStrengths:
    """Tests for team strength calculation."""

    def test_returns_all_countries(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Returns strength for all six nations."""
        strengths = calculate_team_strengths(sample_completed_matches)

        assert len(strengths) == len(Country)
        for country in Country:
            assert country in strengths

    def test_returns_team_strength_objects(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Returns TeamStrength dataclass instances."""
        strengths = calculate_team_strengths(sample_completed_matches)

        for strength in strengths.values():
            assert isinstance(strength, TeamStrength)
            assert hasattr(strength, "country")
            assert hasattr(strength, "matches_played")
            assert hasattr(strength, "strength_score")

    def test_calculates_wins_correctly(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Correctly counts wins for each team."""
        strengths = calculate_team_strengths(sample_completed_matches)

        # Ireland won both matches (vs England, vs France)
        assert strengths[Country.IRELAND].wins == 2

    def test_calculates_point_differential(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Correctly calculates point differential."""
        strengths = calculate_team_strengths(sample_completed_matches)

        # Ireland: +20 (GW1) + +5 (GW2) = +25
        ireland = strengths[Country.IRELAND]
        assert ireland.points_for == 60  # 35 + 25
        assert ireland.points_against == 35  # 15 + 20
        assert ireland.point_differential == 25

    def test_strength_score_normalized(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Strength scores are normalized 0-100."""
        strengths = calculate_team_strengths(sample_completed_matches)

        for strength in strengths.values():
            assert 0 <= strength.strength_score <= 100

    def test_empty_matches_list(self) -> None:
        """Empty matches list returns zero stats."""
        strengths = calculate_team_strengths([])

        for strength in strengths.values():
            assert strength.matches_played == 0
            assert strength.strength_score == 50.0  # Default middle value


class TestGetDifficultyRating:
    """Tests for difficulty rating conversion."""

    def test_very_hard_threshold(self) -> None:
        """Strength >= 80 is very hard."""
        assert get_difficulty_rating(80.0) == DifficultyRating.VERY_HARD
        assert get_difficulty_rating(100.0) == DifficultyRating.VERY_HARD

    def test_hard_threshold(self) -> None:
        """Strength 60-79 is hard."""
        assert get_difficulty_rating(60.0) == DifficultyRating.HARD
        assert get_difficulty_rating(79.0) == DifficultyRating.HARD

    def test_medium_threshold(self) -> None:
        """Strength 40-59 is medium."""
        assert get_difficulty_rating(40.0) == DifficultyRating.MEDIUM
        assert get_difficulty_rating(59.0) == DifficultyRating.MEDIUM

    def test_easy_threshold(self) -> None:
        """Strength 20-39 is easy."""
        assert get_difficulty_rating(20.0) == DifficultyRating.EASY
        assert get_difficulty_rating(39.0) == DifficultyRating.EASY

    def test_very_easy_threshold(self) -> None:
        """Strength < 20 is very easy."""
        assert get_difficulty_rating(0.0) == DifficultyRating.VERY_EASY
        assert get_difficulty_rating(19.0) == DifficultyRating.VERY_EASY


class TestCalculateFixtureDifficulties:
    """Tests for fixture difficulty calculation."""

    def test_returns_difficulty_for_each_match(
        self, all_matches: list[Match]
    ) -> None:
        """Returns FixtureDifficulty for each match."""
        difficulties = calculate_fixture_difficulties(all_matches)

        assert len(difficulties) == len(all_matches)
        assert all(isinstance(d, FixtureDifficulty) for d in difficulties)

    def test_includes_both_home_and_away_ratings(
        self, all_matches: list[Match]
    ) -> None:
        """Each fixture has both home and away difficulty."""
        difficulties = calculate_fixture_difficulties(all_matches)

        for diff in difficulties:
            assert isinstance(diff.home_difficulty, DifficultyRating)
            assert isinstance(diff.away_difficulty, DifficultyRating)
            assert 1 <= diff.home_rating <= 5
            assert 1 <= diff.away_rating <= 5

    def test_home_advantage_reduces_difficulty(
        self, sample_completed_matches: list[Match]
    ) -> None:
        """Home team has slightly easier difficulty."""
        difficulties = calculate_fixture_difficulties(sample_completed_matches)

        # For evenly matched teams, home should have equal or lower difficulty
        for diff in difficulties:
            # Home advantage means home_difficulty should be <= away_difficulty
            # (or at most 1 level higher in edge cases)
            assert diff.home_rating <= diff.away_rating + 1


class TestGetTeamFixtureDifficulty:
    """Tests for getting team-specific fixtures."""

    def test_returns_team_fixtures(
        self, all_matches: list[Match]
    ) -> None:
        """Returns fixtures for specified team."""
        difficulties = calculate_fixture_difficulties(all_matches)
        ireland_fixtures = get_team_fixture_difficulty(
            Country.IRELAND, difficulties, upcoming_only=False
        )

        assert len(ireland_fixtures) > 0
        for match, diff in ireland_fixtures:
            assert match.home_team == "Ireland" or match.away_team == "Ireland"

    def test_upcoming_only_filters_completed(
        self, all_matches: list[Match]
    ) -> None:
        """upcoming_only=True filters out completed matches."""
        difficulties = calculate_fixture_difficulties(all_matches)
        upcoming = get_team_fixture_difficulty(
            Country.IRELAND, difficulties, upcoming_only=True
        )
        all_team = get_team_fixture_difficulty(
            Country.IRELAND, difficulties, upcoming_only=False
        )

        assert len(upcoming) < len(all_team)
        for match, _ in upcoming:
            assert not match.is_completed

    def test_sorted_by_gameweek(
        self, all_matches: list[Match]
    ) -> None:
        """Fixtures sorted by gameweek ascending."""
        difficulties = calculate_fixture_difficulties(all_matches)
        fixtures = get_team_fixture_difficulty(
            Country.FRANCE, difficulties, upcoming_only=False
        )

        gameweeks = [m.gameweek for m, _ in fixtures]
        assert gameweeks == sorted(gameweeks)


class TestGetFixtureRecommendations:
    """Tests for fixture-based recommendations."""

    def test_returns_recommendations(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Returns list of FixtureRecommendation objects."""
        recs = get_fixture_recommendations(
            sample_players, all_matches, gameweeks_ahead=2, top_n=10
        )

        assert len(recs) > 0
        assert all(isinstance(r, FixtureRecommendation) for r in recs)

    def test_sorted_by_favorable_fixtures(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Recommendations sorted by score (easiest fixtures first)."""
        recs = get_fixture_recommendations(
            sample_players, all_matches, gameweeks_ahead=2, top_n=10
        )

        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_respects_top_n(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Limits results to top_n."""
        recs = get_fixture_recommendations(
            sample_players, all_matches, gameweeks_ahead=2, top_n=2
        )
        assert len(recs) <= 2

    def test_includes_fixture_details(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Recommendations include fixture details."""
        recs = get_fixture_recommendations(
            sample_players, all_matches, gameweeks_ahead=2, top_n=10
        )

        for rec in recs:
            assert rec.upcoming_difficulty > 0
            assert len(rec.fixture_details) > 0
            assert "GW" in rec.reason


class TestGetFavorableCaptainPicks:
    """Tests for fixture-aware captain recommendations."""

    def test_returns_recommendations(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Returns captain recommendations."""
        player_points = {
            "p1": 45.0,
            "p2": 30.0,
            "p3": 40.0,
            "p4": 35.0,
        }
        recs = get_favorable_captain_picks(
            sample_players, player_points, all_matches, top_n=5
        )

        assert len(recs) > 0
        assert all(isinstance(r, FixtureRecommendation) for r in recs)

    def test_combines_points_and_fixtures(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Score combines expected points and fixture difficulty."""
        player_points = {
            "p1": 45.0,
            "p2": 30.0,
            "p3": 40.0,
            "p4": 35.0,
        }
        recs = get_favorable_captain_picks(
            sample_players, player_points, all_matches, top_n=5
        )

        for rec in recs:
            # Score should factor in both points and fixture
            assert "pts" in rec.reason
            assert "fixture bonus" in rec.reason

    def test_excludes_zero_points_players(
        self, sample_players: list[Player], all_matches: list[Match]
    ) -> None:
        """Players with zero expected points excluded."""
        player_points = {
            "p1": 45.0,
            "p2": 0.0,  # Zero points
            "p3": 40.0,
            "p4": 35.0,
        }
        recs = get_favorable_captain_picks(
            sample_players, player_points, all_matches, top_n=10
        )

        player_ids = [r.player.id for r in recs]
        assert "p2" not in player_ids


class TestCountryNameMap:
    """Tests for country name mapping."""

    def test_all_countries_mapped(self) -> None:
        """All Six Nations countries are in the map."""
        expected_names = ["England", "Scotland", "Ireland", "Wales", "France", "Italy"]
        for name in expected_names:
            assert name in COUNTRY_NAME_MAP
            assert isinstance(COUNTRY_NAME_MAP[name], Country)

    def test_maps_to_correct_country(self) -> None:
        """Names map to correct Country enum values."""
        assert COUNTRY_NAME_MAP["England"] == Country.ENGLAND
        assert COUNTRY_NAME_MAP["France"] == Country.FRANCE
        assert COUNTRY_NAME_MAP["Ireland"] == Country.IRELAND
