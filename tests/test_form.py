"""Tests for the form tracker module."""

from datetime import date

import pytest

from src.analysis.form import (
    FormRecommendation,
    FormTrend,
    PlayerForm,
    calculate_form_trend,
    get_declining_players,
    get_form_recommendations,
    get_improving_players,
    get_player_form,
)
from src.models import Country, Player, Position
from src.models.match import Match, PlayerMatchStats
from src.models.player import SelectionStatus


@pytest.fixture
def sample_players() -> list[Player]:
    """Create sample players for testing."""
    return [
        Player(
            id="p1",
            name="Antoine Dupont",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=15.0,
        ),
        Player(
            id="p2",
            name="Caelan Doris",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=12.0,
        ),
        Player(
            id="p3",
            name="Tommy Freeman",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=8.0,
        ),
    ]


@pytest.fixture
def sample_matches() -> list[Match]:
    """Create sample matches spanning 3 gameweeks."""
    return [
        Match(
            id="m1",
            home_team="France",
            away_team="Ireland",
            match_date=date(2026, 2, 1),
            gameweek=1,
            home_score=20,
            away_score=15,
        ),
        Match(
            id="m2",
            home_team="England",
            away_team="Scotland",
            match_date=date(2026, 2, 1),
            gameweek=1,
            home_score=25,
            away_score=10,
        ),
        Match(
            id="m3",
            home_team="Ireland",
            away_team="England",
            match_date=date(2026, 2, 8),
            gameweek=2,
            home_score=30,
            away_score=20,
        ),
        Match(
            id="m4",
            home_team="France",
            away_team="Scotland",
            match_date=date(2026, 2, 8),
            gameweek=2,
            home_score=35,
            away_score=5,
        ),
        Match(
            id="m5",
            home_team="France",
            away_team="England",
            match_date=date(2026, 2, 15),
            gameweek=3,
            home_score=28,
            away_score=18,
        ),
    ]


@pytest.fixture
def sample_match_stats() -> list[PlayerMatchStats]:
    """Create match stats showing improving, stable, and declining form."""
    return [
        # p1 (Dupont) - Improving form: 10 -> 15 -> 25 pts
        PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.STARTER,
            tries=0,
            tackles=10,  # 10 pts
        ),
        PlayerMatchStats(
            player_id="p1",
            match_id="m4",
            selection_status=SelectionStatus.STARTER,
            tries=0,
            tackles=10,
            defenders_beaten=2,  # 10 + 4 = 14 pts (rounded)
            offloads=1,  # +2 = 16 pts
        ),
        PlayerMatchStats(
            player_id="p1",
            match_id="m5",
            selection_status=SelectionStatus.STARTER,
            tries=2,  # 20 pts (back)
            tackles=5,  # +5 = 25 pts
        ),
        # p2 (Doris) - Declining form: 30 -> 20 -> 10 pts
        PlayerMatchStats(
            player_id="p2",
            match_id="m1",
            selection_status=SelectionStatus.STARTER,
            tries=2,  # 30 pts (forward)
        ),
        PlayerMatchStats(
            player_id="p2",
            match_id="m3",
            selection_status=SelectionStatus.STARTER,
            tries=1,  # 15 pts
            tackles=5,  # +5 = 20 pts
        ),
        PlayerMatchStats(
            player_id="p2",
            match_id="m5",
            selection_status=SelectionStatus.SUBSTITUTE,
            tackles=10,  # 10 pts
        ),
        # p3 (Freeman) - Stable form: 20 -> 20 -> 20 pts
        PlayerMatchStats(
            player_id="p3",
            match_id="m2",
            selection_status=SelectionStatus.STARTER,
            tries=2,  # 20 pts (back)
        ),
        PlayerMatchStats(
            player_id="p3",
            match_id="m3",
            selection_status=SelectionStatus.STARTER,
            tries=1,  # 10 pts
            tackles=10,  # +10 = 20 pts
        ),
        PlayerMatchStats(
            player_id="p3",
            match_id="m5",
            selection_status=SelectionStatus.STARTER,
            tackles=15,  # 15 pts
            offloads=2,  # +4 = 19 pts
            defenders_beaten=1,  # +2 = 21 pts (close to 20)
        ),
    ]


class TestCalculateFormTrend:
    """Tests for form trend calculation."""

    def test_improving_trend(self) -> None:
        """Higher recent points indicates improvement."""
        # Most recent first: 30, 25, 10, 5
        points = [30.0, 25.0, 10.0, 5.0]
        assert calculate_form_trend(points) == FormTrend.IMPROVING

    def test_declining_trend(self) -> None:
        """Lower recent points indicates decline."""
        # Most recent first: 5, 10, 25, 30
        points = [5.0, 10.0, 25.0, 30.0]
        assert calculate_form_trend(points) == FormTrend.DECLINING

    def test_stable_trend(self) -> None:
        """Similar points indicates stable form."""
        points = [20.0, 21.0, 19.0, 20.0]
        assert calculate_form_trend(points) == FormTrend.STABLE

    def test_single_match_returns_stable(self) -> None:
        """Cannot determine trend from single match."""
        points = [25.0]
        assert calculate_form_trend(points) == FormTrend.STABLE

    def test_empty_list_returns_stable(self) -> None:
        """Empty list returns stable."""
        assert calculate_form_trend([]) == FormTrend.STABLE

    def test_two_matches_can_determine_trend(self) -> None:
        """Two matches can show a trend."""
        assert calculate_form_trend([30.0, 10.0]) == FormTrend.IMPROVING
        assert calculate_form_trend([10.0, 30.0]) == FormTrend.DECLINING


class TestGetPlayerForm:
    """Tests for player form calculation."""

    def test_returns_player_form(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Returns PlayerForm with calculated metrics."""
        player = sample_players[0]  # Dupont
        form = get_player_form(player, sample_match_stats, sample_matches, recent_matches=3)

        assert isinstance(form, PlayerForm)
        assert form.player_id == "p1"
        assert form.matches_played == 3

    def test_calculates_average_points(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Calculates average points across matches."""
        player = sample_players[0]
        form = get_player_form(player, sample_match_stats, sample_matches, recent_matches=3)

        assert form.total_points > 0
        assert form.average_points == form.total_points / form.matches_played

    def test_limits_to_recent_matches(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Only considers specified number of recent matches."""
        player = sample_players[0]
        form = get_player_form(player, sample_match_stats, sample_matches, recent_matches=2)

        assert form.matches_played == 2
        assert len(form.recent_points) == 2

    def test_player_with_no_stats(
        self, sample_matches: list[Match]
    ) -> None:
        """Player with no stats returns zero form."""
        player = Player(
            id="p99",
            name="Unknown",
            country=Country.WALES,
            position=Position.BACK,
            star_value=5.0,
        )
        form = get_player_form(player, [], sample_matches, recent_matches=3)

        assert form.matches_played == 0
        assert form.total_points == 0.0
        assert form.average_points == 0.0
        assert form.trend == FormTrend.STABLE


class TestGetFormRecommendations:
    """Tests for form-based recommendations."""

    def test_returns_recommendations(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Returns list of FormRecommendation objects."""
        recs = get_form_recommendations(
            sample_players, sample_match_stats, sample_matches, top_n=10
        )

        assert len(recs) > 0
        assert all(isinstance(r, FormRecommendation) for r in recs)

    def test_sorted_by_score_descending(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Recommendations sorted by score highest first."""
        recs = get_form_recommendations(
            sample_players, sample_match_stats, sample_matches, top_n=10
        )

        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_respects_min_matches_filter(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Filters out players below min_matches threshold."""
        # All sample players have 3 matches
        recs_with_min_4 = get_form_recommendations(
            sample_players, sample_match_stats, sample_matches, min_matches=4, top_n=10
        )
        assert len(recs_with_min_4) == 0

    def test_respects_top_n(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Limits results to top_n."""
        recs = get_form_recommendations(
            sample_players, sample_match_stats, sample_matches, top_n=1
        )
        assert len(recs) == 1

    def test_includes_trend_in_reason(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Reason string includes form trend."""
        recs = get_form_recommendations(
            sample_players, sample_match_stats, sample_matches
        )

        for rec in recs:
            assert any(
                trend in rec.reason
                for trend in ["improving", "stable", "declining"]
            )


class TestGetImprovingPlayers:
    """Tests for finding improving players."""

    def test_returns_only_improving(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Only returns players with improving trend."""
        recs = get_improving_players(
            sample_players, sample_match_stats, sample_matches, top_n=10
        )

        for rec in recs:
            assert rec.form.trend == FormTrend.IMPROVING


class TestGetDecliningPlayers:
    """Tests for finding declining players."""

    def test_returns_only_declining(
        self, sample_players: list[Player], sample_match_stats: list[PlayerMatchStats], sample_matches: list[Match]
    ) -> None:
        """Only returns players with declining trend."""
        recs = get_declining_players(
            sample_players, sample_match_stats, sample_matches, top_n=10
        )

        for rec in recs:
            assert rec.form.trend == FormTrend.DECLINING
