"""Tests for the recommender module."""

import pytest

from src.analysis.recommender import (
    PlayerRecommendation,
    TransferRecommendation,
    calculate_points_per_star,
    get_captain_recommendations,
    get_differential_picks,
    get_supersub_recommendations,
    get_transfer_out_candidates,
    get_transfer_suggestions,
    get_value_picks,
)
from src.models import Country, Player, Position
from src.models.team import Team


@pytest.fixture
def sample_players() -> list[Player]:
    """Create a set of sample players for testing."""
    return [
        Player(
            id="p1",
            name="Antoine Dupont",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=15.0,
            ownership_pct=45.0,
        ),
        Player(
            id="p2",
            name="Caelan Doris",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=12.0,
            ownership_pct=30.0,
        ),
        Player(
            id="p3",
            name="Tommy Freeman",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=8.0,
            ownership_pct=5.0,
        ),
        Player(
            id="p4",
            name="Damian Penaud",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=10.0,
            ownership_pct=20.0,
        ),
        Player(
            id="p5",
            name="Tadhg Furlong",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=11.0,
            ownership_pct=25.0,
        ),
    ]


@pytest.fixture
def player_points() -> dict[str, float]:
    """Sample historical points data."""
    return {
        "p1": 45.0,  # Dupont: 3.0 pts/star
        "p2": 36.0,  # Doris: 3.0 pts/star
        "p3": 32.0,  # Freeman: 4.0 pts/star (best value)
        "p4": 20.0,  # Penaud: 2.0 pts/star
        "p5": 22.0,  # Furlong: 2.0 pts/star
    }


@pytest.fixture
def sample_team(sample_players: list[Player]) -> Team:
    """Create a sample team with 5 players."""
    team = Team()
    for player in sample_players:
        team.add_player(player)
    team.set_captain("p1")  # Dupont as captain
    return team


class TestCalculatePointsPerStar:
    """Tests for points per star calculation."""

    def test_normal_calculation(self) -> None:
        """Test standard calculation."""
        assert calculate_points_per_star(30.0, 10.0) == 3.0

    def test_zero_star_value(self) -> None:
        """Zero star value returns 0."""
        assert calculate_points_per_star(30.0, 0.0) == 0.0

    def test_negative_star_value(self) -> None:
        """Negative star value returns 0."""
        assert calculate_points_per_star(30.0, -5.0) == 0.0

    def test_zero_points(self) -> None:
        """Zero points returns 0."""
        assert calculate_points_per_star(0.0, 10.0) == 0.0


class TestGetCaptainRecommendations:
    """Tests for captain recommendation functionality."""

    def test_returns_recommendations(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should return PlayerRecommendation objects."""
        recs = get_captain_recommendations(sample_team, player_points)
        assert len(recs) > 0
        assert all(isinstance(r, PlayerRecommendation) for r in recs)

    def test_sorted_by_expected_points(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Recommendations should be sorted by captain points descending."""
        recs = get_captain_recommendations(sample_team, player_points)
        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_captain_multiplier_applied(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Captain score should be 2x base points."""
        recs = get_captain_recommendations(sample_team, player_points)
        # Dupont has 45 base points, so captain score = 90
        dupont_rec = next((r for r in recs if r.player.id == "p1"), None)
        assert dupont_rec is not None
        assert dupont_rec.score == 90.0

    def test_excludes_supersub(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should exclude current supersub from recommendations."""
        sample_team.set_supersub("p2")
        recs = get_captain_recommendations(sample_team, player_points)
        player_ids = [r.player.id for r in recs]
        assert "p2" not in player_ids

    def test_empty_team(self, player_points: dict[str, float]) -> None:
        """Empty team returns empty list."""
        empty_team = Team()
        recs = get_captain_recommendations(empty_team, player_points)
        assert recs == []

    def test_top_n_limit(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should respect top_n limit."""
        recs = get_captain_recommendations(sample_team, player_points, top_n=2)
        assert len(recs) <= 2


class TestGetSupersubRecommendations:
    """Tests for supersub recommendation functionality."""

    def test_returns_recommendations(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should return PlayerRecommendation objects."""
        recs = get_supersub_recommendations(sample_team, player_points)
        assert len(recs) > 0

    def test_excludes_captain(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should exclude current captain."""
        recs = get_supersub_recommendations(sample_team, player_points)
        player_ids = [r.player.id for r in recs]
        assert sample_team.captain_id not in player_ids

    def test_uses_sub_probability(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should use provided sub probability."""
        # p3 has 32 points
        # With 100% sub prob: 32 * 3.0 = 96
        sub_prob = {"p3": 1.0}
        recs = get_supersub_recommendations(
            sample_team, player_points, sub_probability=sub_prob
        )
        freeman_rec = next((r for r in recs if r.player.id == "p3"), None)
        assert freeman_rec is not None
        assert freeman_rec.score == 96.0

    def test_default_probability(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Default 50% probability gives expected multiplier of 1.75."""
        sample_team.captain_id = None  # Remove captain so p1 is eligible
        recs = get_supersub_recommendations(sample_team, player_points)
        # p1 has 45 points, 50% prob gives 0.5*3.0 + 0.5*0.5 = 1.75x
        dupont_rec = next((r for r in recs if r.player.id == "p1"), None)
        assert dupont_rec is not None
        assert dupont_rec.score == pytest.approx(45.0 * 1.75)


class TestGetValuePicks:
    """Tests for value pick recommendations."""

    def test_returns_high_value_players(
        self, sample_players: list[Player], player_points: dict[str, float]
    ) -> None:
        """Should return players sorted by points per star."""
        recs = get_value_picks(sample_players, player_points)
        # Freeman (p3) has 4.0 pts/star, should be first
        assert recs[0].player.id == "p3"
        assert recs[0].score == 4.0

    def test_excludes_team_players(
        self,
        sample_players: list[Player],
        sample_team: Team,
        player_points: dict[str, float],
    ) -> None:
        """Should exclude players already in team."""
        recs = get_value_picks(sample_players, player_points, team=sample_team)
        assert len(recs) == 0  # All players are in the team

    def test_respects_team_constraints(
        self, player_points: dict[str, float]
    ) -> None:
        """Should not recommend players that violate constraints."""
        # Create a team at budget limit
        team = Team()
        team.add_player(
            Player(
                id="rich",
                name="Expensive Player",
                country=Country.ENGLAND,
                position=Position.BACK,
                star_value=195.0,
            )
        )

        # Available player too expensive
        expensive = Player(
            id="p10",
            name="Too Expensive",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=10.0,
        )

        recs = get_value_picks([expensive], {"p10": 50.0}, team=team)
        assert len(recs) == 0  # Can't afford

    def test_skips_zero_value(self, sample_players: list[Player]) -> None:
        """Players with 0 points should not be recommended."""
        recs = get_value_picks(sample_players, {"p1": 0.0})
        player_ids = [r.player.id for r in recs]
        assert "p1" not in player_ids


class TestGetTransferOutCandidates:
    """Tests for transfer out recommendations."""

    def test_returns_low_value_first(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should return lowest value players first."""
        recs = get_transfer_out_candidates(sample_team, player_points)
        # p4 and p5 both have 2.0 pts/star (lowest)
        assert recs[0].score == pytest.approx(2.0)

    def test_notes_captain_status(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should note if player is captain."""
        recs = get_transfer_out_candidates(sample_team, player_points)
        captain_rec = next((r for r in recs if r.player.id == "p1"), None)
        assert captain_rec is not None
        assert "captain" in captain_rec.reason

    def test_notes_supersub_status(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should note if player is supersub."""
        sample_team.set_supersub("p2")
        recs = get_transfer_out_candidates(sample_team, player_points)
        supersub_rec = next((r for r in recs if r.player.id == "p2"), None)
        assert supersub_rec is not None
        assert "supersub" in supersub_rec.reason

    def test_empty_team(self, player_points: dict[str, float]) -> None:
        """Empty team returns empty list."""
        recs = get_transfer_out_candidates(Team(), player_points)
        assert recs == []


class TestGetTransferSuggestions:
    """Tests for transfer suggestion functionality."""

    def test_suggests_value_improvements(
        self, player_points: dict[str, float]
    ) -> None:
        """Should suggest transfers that improve value."""
        # Team with low-value player
        team = Team()
        low_value = Player(
            id="low",
            name="Low Value",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=10.0,
        )
        team.add_player(low_value)

        # Available high-value replacement
        high_value = Player(
            id="high",
            name="High Value",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=10.0,
        )

        points = {"low": 10.0, "high": 40.0}  # 1.0 vs 4.0 pts/star

        suggestions = get_transfer_suggestions(team, [high_value], points)
        assert len(suggestions) == 1
        assert suggestions[0].player_out.id == "low"
        assert suggestions[0].player_in.id == "high"
        assert suggestions[0].value_gain == pytest.approx(3.0)

    def test_no_suggestions_if_no_improvement(
        self, sample_team: Team, player_points: dict[str, float]
    ) -> None:
        """Should not suggest transfers that decrease value."""
        # Available player with worse value than anyone in team
        bad_value = Player(
            id="bad",
            name="Bad Value",
            country=Country.SCOTLAND,
            position=Position.BACK,
            star_value=10.0,
        )

        suggestions = get_transfer_suggestions(
            sample_team, [bad_value], {**player_points, "bad": 5.0}  # 0.5 pts/star
        )
        assert len(suggestions) == 0

    def test_respects_budget(self, player_points: dict[str, float]) -> None:
        """Should not suggest transfers that exceed budget."""
        team = Team()
        # Player worth 5 stars (this is the only one we could transfer out)
        cheap = Player(
            id="cheap",
            name="Cheap",
            country=Country.WALES,
            position=Position.BACK,
            star_value=5.0,
        )
        # Fill budget to 200 exactly
        filler = Player(
            id="filler",
            name="Filler",
            country=Country.ITALY,
            position=Position.FORWARD,
            star_value=195.0,
        )
        team.add_player(cheap)
        team.add_player(filler)

        # Replacement is too expensive - costs more than cheap player releases
        expensive = Player(
            id="exp",
            name="Expensive",
            country=Country.WALES,
            position=Position.BACK,
            star_value=10.0,
        )

        # Simulate filler having 0 points (so no improvement possible for filler swap)
        # Only check if cheap -> expensive works (it shouldn't due to budget)
        suggestions = get_transfer_suggestions(
            team, [expensive], {"cheap": 5.0, "filler": 0.0, "exp": 50.0}
        )
        # cheap (5 stars) -> expensive (10 stars) needs 5 extra stars
        # budget_remaining is 0, so can't afford
        # filler (195 stars) -> expensive (10 stars) would work budget-wise,
        # but filler has 0 points so exp (5.0 pts/star) > filler (0 pts/star) = suggests it
        # Filter to only transfers from cheap
        cheap_transfers = [s for s in suggestions if s.player_out.id == "cheap"]
        assert len(cheap_transfers) == 0

    def test_returns_transfer_recommendation_type(
        self, player_points: dict[str, float]
    ) -> None:
        """Should return TransferRecommendation objects."""
        team = Team()
        p1 = Player(
            id="out",
            name="Out",
            country=Country.WALES,
            position=Position.BACK,
            star_value=10.0,
        )
        team.add_player(p1)

        p2 = Player(
            id="in",
            name="In",
            country=Country.WALES,
            position=Position.BACK,
            star_value=10.0,
        )

        suggestions = get_transfer_suggestions(
            team, [p2], {"out": 10.0, "in": 50.0}
        )
        assert len(suggestions) == 1
        assert isinstance(suggestions[0], TransferRecommendation)


class TestGetDifferentialPicks:
    """Tests for differential pick recommendations."""

    def test_returns_low_ownership_players(
        self, sample_players: list[Player], player_points: dict[str, float]
    ) -> None:
        """Should return players below ownership threshold."""
        recs = get_differential_picks(
            sample_players, player_points, max_ownership=10.0
        )
        # Only p3 (Freeman) has 5% ownership < 10%
        assert len(recs) == 1
        assert recs[0].player.id == "p3"

    def test_excludes_high_ownership(
        self, sample_players: list[Player], player_points: dict[str, float]
    ) -> None:
        """Should exclude players above ownership threshold."""
        recs = get_differential_picks(
            sample_players, player_points, max_ownership=5.0
        )
        assert len(recs) == 0

    def test_excludes_no_ownership_data(
        self, player_points: dict[str, float]
    ) -> None:
        """Should exclude players without ownership data."""
        no_ownership = Player(
            id="no_own",
            name="No Ownership",
            country=Country.ITALY,
            position=Position.BACK,
            star_value=8.0,
            ownership_pct=None,
        )
        recs = get_differential_picks([no_ownership], player_points)
        assert len(recs) == 0

    def test_excludes_zero_points(self, sample_players: list[Player]) -> None:
        """Should exclude players with no points."""
        recs = get_differential_picks(
            sample_players, {"p3": 0.0}, max_ownership=10.0
        )
        assert len(recs) == 0

    def test_excludes_team_players(
        self,
        sample_players: list[Player],
        sample_team: Team,
        player_points: dict[str, float],
    ) -> None:
        """Should exclude players already in team."""
        recs = get_differential_picks(
            sample_players, player_points, max_ownership=50.0, team=sample_team
        )
        assert len(recs) == 0
