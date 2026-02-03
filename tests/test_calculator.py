"""Tests for fantasy points calculator."""

import pytest

from src.analysis.calculator import (
    BonusRole,
    PointsBreakdown,
    calculate_base_points,
    calculate_multiplier,
    calculate_player_points,
    calculate_points,
    POINTS_TRY_BACK,
    POINTS_TRY_FORWARD,
    POINTS_TRY_ASSIST,
    POINTS_CONVERSION,
    POINTS_PENALTY_KICK,
    POINTS_DROP_GOAL,
    POINTS_DEFENDERS_BEATEN,
    POINTS_METRES_PER_10,
    POINTS_FIFTY_22_KICK,
    POINTS_KICK_RETAINED,
    POINTS_OFFLOAD,
    POINTS_SCRUM_WIN,
    POINTS_TACKLE,
    POINTS_BREAKDOWN_STEAL,
    POINTS_LINEOUT_STEAL,
    POINTS_PENALTY_CONCEDED,
    POINTS_PLAYER_OF_MATCH,
    POINTS_YELLOW_CARD,
    POINTS_RED_CARD,
    MULTIPLIER_CAPTAIN,
    MULTIPLIER_SUPERSUB_SUBBED,
    MULTIPLIER_SUPERSUB_NOT_SUBBED,
)
from src.models import Country, Player, PlayerMatchStats, Position, SelectionStatus


class TestScoringConstants:
    """Verify scoring constants match SPEC.md values."""

    def test_attacking_constants(self) -> None:
        """Verify attacking action point values."""
        assert POINTS_TRY_BACK == 10
        assert POINTS_TRY_FORWARD == 15
        assert POINTS_TRY_ASSIST == 4
        assert POINTS_CONVERSION == 2
        assert POINTS_PENALTY_KICK == 3
        assert POINTS_DROP_GOAL == 5
        assert POINTS_DEFENDERS_BEATEN == 2
        assert POINTS_METRES_PER_10 == 1
        assert POINTS_FIFTY_22_KICK == 7
        assert POINTS_KICK_RETAINED == 2
        assert POINTS_OFFLOAD == 2
        assert POINTS_SCRUM_WIN == 1

    def test_defensive_constants(self) -> None:
        """Verify defensive action point values."""
        assert POINTS_TACKLE == 1
        assert POINTS_BREAKDOWN_STEAL == 5
        assert POINTS_LINEOUT_STEAL == 7
        assert POINTS_PENALTY_CONCEDED == -1

    def test_general_constants(self) -> None:
        """Verify general point values."""
        assert POINTS_PLAYER_OF_MATCH == 15
        assert POINTS_YELLOW_CARD == -5
        assert POINTS_RED_CARD == -8

    def test_multiplier_constants(self) -> None:
        """Verify bonus role multipliers."""
        assert MULTIPLIER_CAPTAIN == 2.0
        assert MULTIPLIER_SUPERSUB_SUBBED == 3.0
        assert MULTIPLIER_SUPERSUB_NOT_SUBBED == 0.5


class TestCalculateBasePoints:
    """Tests for calculate_base_points function."""

    def test_zero_stats_returns_zero(self) -> None:
        """Empty stats should return 0 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1")
        points = calculate_base_points(stats, Position.BACK)
        assert points == 0

    def test_try_scoring_back(self) -> None:
        """Back scores 10 points per try."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=2)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 20

    def test_try_scoring_forward(self) -> None:
        """Forward scores 15 points per try."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=2)
        points = calculate_base_points(stats, Position.FORWARD)
        assert points == 30

    def test_try_assist(self) -> None:
        """Try assist scores 4 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", try_assists=3)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 12

    def test_kicking_points(self) -> None:
        """Test conversion, penalty, and drop goal scoring."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            conversions=5,
            penalty_kicks=3,
            drop_goals=1,
        )
        points = calculate_base_points(stats, Position.BACK)
        # 5*2 + 3*3 + 1*5 = 10 + 9 + 5 = 24
        assert points == 24

    def test_metres_carried(self) -> None:
        """Metres carried scores 1 point per 10 metres."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", metres_carried=55)
        points = calculate_base_points(stats, Position.BACK)
        # 55 // 10 = 5 points
        assert points == 5

    def test_metres_carried_under_10(self) -> None:
        """Under 10 metres scores 0."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", metres_carried=9)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 0

    def test_defenders_beaten(self) -> None:
        """Defenders beaten scores 2 per defender."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", defenders_beaten=4)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 8

    def test_fifty_22_kick(self) -> None:
        """50-22 kick scores 7 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", fifty_22_kicks=2)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 14

    def test_kicks_retained(self) -> None:
        """Kick retained scores 2 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", kicks_retained=3)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 6

    def test_offloads(self) -> None:
        """Offload scores 2 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", offloads=5)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 10

    def test_scrum_wins_forward(self) -> None:
        """Scrum wins score 1 point for forwards."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", scrum_wins=8)
        points = calculate_base_points(stats, Position.FORWARD)
        assert points == 8

    def test_scrum_wins_back_ignored(self) -> None:
        """Scrum wins don't count for backs."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", scrum_wins=8)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 0

    def test_tackles(self) -> None:
        """Tackle scores 1 point."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tackles=15)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 15

    def test_breakdown_steal(self) -> None:
        """Breakdown steal scores 5 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", breakdown_steals=2)
        points = calculate_base_points(stats, Position.FORWARD)
        assert points == 10

    def test_lineout_steal(self) -> None:
        """Lineout steal scores 7 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", lineout_steals=1)
        points = calculate_base_points(stats, Position.FORWARD)
        assert points == 7

    def test_penalties_conceded(self) -> None:
        """Penalty conceded loses 1 point."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", penalties_conceded=3)
        points = calculate_base_points(stats, Position.BACK)
        assert points == -3

    def test_player_of_match(self) -> None:
        """Player of the Match scores 15 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", player_of_match=True)
        points = calculate_base_points(stats, Position.BACK)
        assert points == 15

    def test_yellow_card(self) -> None:
        """Yellow card loses 5 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", yellow_cards=1)
        points = calculate_base_points(stats, Position.BACK)
        assert points == -5

    def test_red_card(self) -> None:
        """Red card loses 8 points."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", red_cards=1)
        points = calculate_base_points(stats, Position.BACK)
        assert points == -8

    def test_comprehensive_stats(self) -> None:
        """Test a realistic stat line."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.STARTER,
            tries=1,
            try_assists=1,
            conversions=0,
            penalty_kicks=0,
            drop_goals=0,
            metres_carried=45,
            defenders_beaten=3,
            offloads=2,
            fifty_22_kicks=0,
            kicks_retained=0,
            scrum_wins=0,
            tackles=8,
            breakdown_steals=1,
            lineout_steals=0,
            penalties_conceded=1,
            yellow_cards=0,
            red_cards=0,
            player_of_match=False,
        )
        points = calculate_base_points(stats, Position.BACK)
        # try: 10, assist: 4, metres: 4, defenders: 6, offloads: 4, tackles: 8, steal: 5, penalty: -1
        # 10 + 4 + 4 + 6 + 4 + 8 + 5 - 1 = 40
        assert points == 40


class TestCalculateMultiplier:
    """Tests for calculate_multiplier function."""

    def test_no_role(self) -> None:
        """No role returns 1.0 multiplier."""
        mult = calculate_multiplier(BonusRole.NONE, was_substitute=False)
        assert mult == 1.0

    def test_captain(self) -> None:
        """Captain returns 2.0 multiplier."""
        mult = calculate_multiplier(BonusRole.CAPTAIN, was_substitute=False)
        assert mult == 2.0

    def test_captain_as_sub(self) -> None:
        """Captain as substitute still gets 2.0."""
        mult = calculate_multiplier(BonusRole.CAPTAIN, was_substitute=True)
        assert mult == 2.0

    def test_supersub_entered_as_sub(self) -> None:
        """Supersub who entered as substitute gets 3.0."""
        mult = calculate_multiplier(BonusRole.SUPERSUB, was_substitute=True)
        assert mult == 3.0

    def test_supersub_started(self) -> None:
        """Supersub who started gets 0.5."""
        mult = calculate_multiplier(BonusRole.SUPERSUB, was_substitute=False)
        assert mult == 0.5


class TestCalculatePoints:
    """Tests for calculate_points function with breakdown."""

    def test_returns_breakdown(self) -> None:
        """Function returns PointsBreakdown dataclass."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=1)
        result = calculate_points(stats, Position.BACK)
        assert isinstance(result, PointsBreakdown)

    def test_breakdown_no_role(self) -> None:
        """Test breakdown without bonus role."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=1)
        result = calculate_points(stats, Position.BACK)
        assert result.base_points == 10
        assert result.multiplier == 1.0
        assert result.final_points == 10
        assert result.role == BonusRole.NONE

    def test_breakdown_captain(self) -> None:
        """Test breakdown with captain role."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=1)
        result = calculate_points(stats, Position.BACK, BonusRole.CAPTAIN)
        assert result.base_points == 10
        assert result.multiplier == 2.0
        assert result.final_points == 20
        assert result.role == BonusRole.CAPTAIN

    def test_breakdown_supersub_as_sub(self) -> None:
        """Test breakdown with supersub who entered as substitute."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.SUBSTITUTE,
            tries=1,
        )
        result = calculate_points(stats, Position.BACK, BonusRole.SUPERSUB)
        assert result.base_points == 10
        assert result.multiplier == 3.0
        assert result.final_points == 30
        assert result.role == BonusRole.SUPERSUB

    def test_breakdown_supersub_started(self) -> None:
        """Test breakdown with supersub who started (penalty)."""
        stats = PlayerMatchStats(
            player_id="p1",
            match_id="m1",
            selection_status=SelectionStatus.STARTER,
            tries=2,
        )
        result = calculate_points(stats, Position.BACK, BonusRole.SUPERSUB)
        assert result.base_points == 20
        assert result.multiplier == 0.5
        assert result.final_points == 10
        assert result.role == BonusRole.SUPERSUB


class TestCalculatePlayerPoints:
    """Tests for calculate_player_points convenience function."""

    @pytest.fixture
    def back_player(self) -> Player:
        """Create a sample back player."""
        return Player(
            id="p1",
            name="Antoine Dupont",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=15.0,
        )

    @pytest.fixture
    def forward_player(self) -> Player:
        """Create a sample forward player."""
        return Player(
            id="p2",
            name="Tadhg Furlong",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=12.0,
        )

    def test_uses_player_position_back(self, back_player: Player) -> None:
        """Verify back position is used from Player object."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tries=1)
        result = calculate_player_points(back_player, stats)
        assert result.base_points == 10  # Back try value

    def test_uses_player_position_forward(self, forward_player: Player) -> None:
        """Verify forward position is used from Player object."""
        stats = PlayerMatchStats(player_id="p2", match_id="m1", tries=1)
        result = calculate_player_points(forward_player, stats)
        assert result.base_points == 15  # Forward try value

    def test_with_captain_role(self, back_player: Player) -> None:
        """Test with captain role applied."""
        stats = PlayerMatchStats(player_id="p1", match_id="m1", tackles=10)
        result = calculate_player_points(back_player, stats, BonusRole.CAPTAIN)
        assert result.base_points == 10
        assert result.final_points == 20
