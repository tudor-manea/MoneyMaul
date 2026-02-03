"""Fantasy points calculator based on Six Nations scoring rules."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..models.match import PlayerMatchStats
from ..models.player import Player, Position


class BonusRole(Enum):
    """Special roles that apply point multipliers."""

    NONE = "none"
    CAPTAIN = "captain"
    SUPERSUB = "supersub"


# Scoring constants from SPEC.md
POINTS_TRY_BACK = 10
POINTS_TRY_FORWARD = 15
POINTS_TRY_ASSIST = 4
POINTS_CONVERSION = 2
POINTS_PENALTY_KICK = 3
POINTS_DROP_GOAL = 5
POINTS_DEFENDERS_BEATEN = 2
POINTS_METRES_PER_10 = 1
POINTS_FIFTY_22_KICK = 7
POINTS_KICK_RETAINED = 2
POINTS_OFFLOAD = 2
POINTS_SCRUM_WIN = 1

POINTS_TACKLE = 1
POINTS_BREAKDOWN_STEAL = 5
POINTS_LINEOUT_STEAL = 7
POINTS_PENALTY_CONCEDED = -1

POINTS_PLAYER_OF_MATCH = 15
POINTS_YELLOW_CARD = -5
POINTS_RED_CARD = -8

MULTIPLIER_CAPTAIN = 2.0
MULTIPLIER_SUPERSUB_SUBBED = 3.0
MULTIPLIER_SUPERSUB_NOT_SUBBED = 0.5


@dataclass
class PointsBreakdown:
    """
    Detailed breakdown of fantasy points earned.

    Attributes:
        base_points: Points before any multipliers.
        multiplier: Multiplier applied (1.0, 2.0, 3.0, or 0.5).
        final_points: Total points after multiplier.
        role: The bonus role applied (if any).
    """

    base_points: float
    multiplier: float
    final_points: float
    role: BonusRole = BonusRole.NONE


def calculate_base_points(
    stats: PlayerMatchStats,
    position: Position,
) -> float:
    """
    Calculate base fantasy points from match statistics.

    Args:
        stats: Player's match statistics.
        position: Player's position (forward/back) for try scoring.

    Returns:
        Total base points before any multipliers.
    """
    points = 0.0

    # Attacking actions
    try_points = POINTS_TRY_FORWARD if position == Position.FORWARD else POINTS_TRY_BACK
    points += stats.tries * try_points
    points += stats.try_assists * POINTS_TRY_ASSIST
    points += stats.conversions * POINTS_CONVERSION
    points += stats.penalty_kicks * POINTS_PENALTY_KICK
    points += stats.drop_goals * POINTS_DROP_GOAL
    points += stats.defenders_beaten * POINTS_DEFENDERS_BEATEN
    points += (stats.metres_carried // 10) * POINTS_METRES_PER_10
    points += stats.fifty_22_kicks * POINTS_FIFTY_22_KICK
    points += stats.kicks_retained * POINTS_KICK_RETAINED
    points += stats.offloads * POINTS_OFFLOAD

    # Scrum wins only count for forwards
    if position == Position.FORWARD:
        points += stats.scrum_wins * POINTS_SCRUM_WIN

    # Defensive actions
    points += stats.tackles * POINTS_TACKLE
    points += stats.breakdown_steals * POINTS_BREAKDOWN_STEAL
    points += stats.lineout_steals * POINTS_LINEOUT_STEAL
    points += stats.penalties_conceded * POINTS_PENALTY_CONCEDED

    # General
    if stats.player_of_match:
        points += POINTS_PLAYER_OF_MATCH
    points += stats.yellow_cards * POINTS_YELLOW_CARD
    points += stats.red_cards * POINTS_RED_CARD

    return points


def calculate_multiplier(
    role: BonusRole,
    was_substitute: bool,
) -> float:
    """
    Determine the point multiplier based on role and selection.

    Args:
        role: The bonus role assigned to the player.
        was_substitute: Whether the player entered as a substitute.

    Returns:
        The multiplier to apply to base points.
    """
    if role == BonusRole.CAPTAIN:
        return MULTIPLIER_CAPTAIN
    elif role == BonusRole.SUPERSUB:
        return MULTIPLIER_SUPERSUB_SUBBED if was_substitute else MULTIPLIER_SUPERSUB_NOT_SUBBED
    return 1.0


def calculate_points(
    stats: PlayerMatchStats,
    position: Position,
    role: BonusRole = BonusRole.NONE,
) -> PointsBreakdown:
    """
    Calculate total fantasy points with full breakdown.

    Args:
        stats: Player's match statistics.
        position: Player's position (forward/back).
        role: Bonus role (captain/supersub) if applicable.

    Returns:
        PointsBreakdown with base points, multiplier, and final total.
    """
    base_points = calculate_base_points(stats, position)
    multiplier = calculate_multiplier(role, stats.was_substitute)
    final_points = base_points * multiplier

    return PointsBreakdown(
        base_points=base_points,
        multiplier=multiplier,
        final_points=final_points,
        role=role,
    )


def calculate_player_points(
    player: Player,
    stats: PlayerMatchStats,
    role: BonusRole = BonusRole.NONE,
) -> PointsBreakdown:
    """
    Convenience function to calculate points using Player object.

    Args:
        player: The Player object.
        stats: Player's match statistics.
        role: Bonus role (captain/supersub) if applicable.

    Returns:
        PointsBreakdown with base points, multiplier, and final total.
    """
    return calculate_points(stats, player.position, role)
