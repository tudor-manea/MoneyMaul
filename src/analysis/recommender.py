"""Recommender module for captain selection and transfer suggestions."""

from dataclasses import dataclass
from typing import Optional

from ..models.player import Player
from ..models.team import Team
from .calculator import MULTIPLIER_CAPTAIN
from .validator import can_add_player, can_make_transfer, find_affordable_transfers


@dataclass
class PlayerRecommendation:
    """
    A recommendation for a player with associated metrics.

    Attributes:
        player: The recommended player.
        score: Recommendation score (higher is better).
        reason: Human-readable explanation for the recommendation.
    """

    player: Player
    score: float
    reason: str


@dataclass
class TransferRecommendation:
    """
    A transfer recommendation suggesting a player swap.

    Attributes:
        player_out: Player to transfer out.
        player_in: Player to transfer in.
        value_gain: Change in points per star ratio.
        reason: Human-readable explanation.
    """

    player_out: Player
    player_in: Player
    value_gain: float
    reason: str


def calculate_points_per_star(total_points: float, star_value: float) -> float:
    """
    Calculate the value metric: points per star.

    Args:
        total_points: Total fantasy points scored.
        star_value: Player's star value (price).

    Returns:
        Points per star ratio. Returns 0 if star_value is 0.
    """
    if star_value <= 0:
        return 0.0
    return total_points / star_value


def get_captain_recommendations(
    team: Team,
    player_points: dict[str, float],
    top_n: int = 5,
) -> list[PlayerRecommendation]:
    """
    Recommend captain picks based on expected points.

    The captain receives a 2x multiplier, so we want to pick the player
    most likely to score the most points.

    Args:
        team: The current fantasy team.
        player_points: Dict mapping player_id to their total/expected points.
        top_n: Number of recommendations to return.

    Returns:
        List of PlayerRecommendation objects, sorted by expected captain value.
    """
    if not team.players:
        return []

    recommendations: list[PlayerRecommendation] = []

    for player in team.players:
        # Skip if already supersub (can't be both)
        if team.supersub_id == player.id:
            continue

        base_points = player_points.get(player.id, 0.0)
        captain_points = base_points * MULTIPLIER_CAPTAIN
        extra_points = captain_points - base_points

        recommendations.append(
            PlayerRecommendation(
                player=player,
                score=captain_points,
                reason=f"Expected {captain_points:.1f} pts as captain "
                f"(+{extra_points:.1f} from 2x multiplier)",
            )
        )

    # Sort by score descending
    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]


def get_supersub_recommendations(
    team: Team,
    player_points: dict[str, float],
    sub_probability: dict[str, float] | None = None,
    top_n: int = 5,
) -> list[PlayerRecommendation]:
    """
    Recommend supersub picks based on expected value.

    The supersub gets 3x if they enter as a substitute, 0.5x otherwise.
    Ideal supersubs are impact players who often come off the bench.

    Args:
        team: The current fantasy team.
        player_points: Dict mapping player_id to their total/expected points.
        sub_probability: Optional dict of player_id -> probability of being subbed on.
                        If not provided, assumes 50% probability for all.
        top_n: Number of recommendations to return.

    Returns:
        List of PlayerRecommendation objects for supersub selection.
    """
    if not team.players:
        return []

    recommendations: list[PlayerRecommendation] = []
    default_sub_prob = 0.5

    for player in team.players:
        # Skip if already captain (can't be both)
        if team.captain_id == player.id:
            continue

        base_points = player_points.get(player.id, 0.0)
        prob = (
            sub_probability.get(player.id, default_sub_prob)
            if sub_probability
            else default_sub_prob
        )

        # Expected value: prob * 3x + (1-prob) * 0.5x
        expected_multiplier = (prob * 3.0) + ((1 - prob) * 0.5)
        expected_points = base_points * expected_multiplier

        recommendations.append(
            PlayerRecommendation(
                player=player,
                score=expected_points,
                reason=f"Expected {expected_points:.1f} pts "
                f"({prob*100:.0f}% sub chance, {expected_multiplier:.2f}x avg)",
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]


def get_value_picks(
    available_players: list[Player],
    player_points: dict[str, float],
    team: Team | None = None,
    top_n: int = 10,
) -> list[PlayerRecommendation]:
    """
    Find high-value players based on points per star ratio.

    Args:
        available_players: List of all available players.
        player_points: Dict mapping player_id to their total points.
        team: Optional current team (to check if player can be added).
        top_n: Number of recommendations to return.

    Returns:
        List of PlayerRecommendation for high-value players.
    """
    recommendations: list[PlayerRecommendation] = []

    for player in available_players:
        # Skip players already in team
        if team and team.get_player(player.id) is not None:
            continue

        # Skip if can't add to team (budget/country limits)
        if team:
            validation = can_add_player(team, player)
            if not validation.is_valid:
                continue

        total_points = player_points.get(player.id, 0.0)
        value = calculate_points_per_star(total_points, player.star_value)

        if value > 0:
            recommendations.append(
                PlayerRecommendation(
                    player=player,
                    score=value,
                    reason=f"{total_points:.1f} pts / {player.star_value:.1f}★ = "
                    f"{value:.2f} pts/★",
                )
            )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]


def get_transfer_out_candidates(
    team: Team,
    player_points: dict[str, float],
    top_n: int = 5,
) -> list[PlayerRecommendation]:
    """
    Identify players in the team with low value for transfer out.

    Args:
        team: The current fantasy team.
        player_points: Dict mapping player_id to their total points.
        top_n: Number of recommendations to return.

    Returns:
        List of PlayerRecommendation for low-value players (lowest first).
    """
    if not team.players:
        return []

    recommendations: list[PlayerRecommendation] = []

    for player in team.players:
        total_points = player_points.get(player.id, 0.0)
        value = calculate_points_per_star(total_points, player.star_value)

        role_note = ""
        if team.captain_id == player.id:
            role_note = " (current captain)"
        elif team.supersub_id == player.id:
            role_note = " (current supersub)"

        recommendations.append(
            PlayerRecommendation(
                player=player,
                score=value,
                reason=f"{total_points:.1f} pts / {player.star_value:.1f}★ = "
                f"{value:.2f} pts/★{role_note}",
            )
        )

    # Sort by value ascending (lowest value = best transfer out candidate)
    recommendations.sort(key=lambda r: r.score)
    return recommendations[:top_n]


def get_transfer_suggestions(
    team: Team,
    available_players: list[Player],
    player_points: dict[str, float],
    top_n: int = 5,
) -> list[TransferRecommendation]:
    """
    Suggest transfers that would improve the team's value.

    Analyzes current squad and available players to find swaps
    that increase overall points-per-star efficiency.

    Args:
        team: The current fantasy team.
        available_players: All available players (pool to choose from).
        player_points: Dict mapping player_id to their total points.
        top_n: Number of transfer suggestions to return.

    Returns:
        List of TransferRecommendation objects, sorted by value gain.
    """
    if not team.players:
        return []

    suggestions: list[TransferRecommendation] = []

    for player_out in team.players:
        out_points = player_points.get(player_out.id, 0.0)
        out_value = calculate_points_per_star(out_points, player_out.star_value)

        # Find valid replacements
        candidates = find_affordable_transfers(team, player_out, available_players)

        for player_in in candidates:
            # Validate the transfer
            validation = can_make_transfer(team, player_out.id, player_in)
            if not validation.is_valid:
                continue

            in_points = player_points.get(player_in.id, 0.0)
            in_value = calculate_points_per_star(in_points, player_in.star_value)
            value_gain = in_value - out_value

            # Only suggest if it improves value
            if value_gain > 0:
                suggestions.append(
                    TransferRecommendation(
                        player_out=player_out,
                        player_in=player_in,
                        value_gain=value_gain,
                        reason=f"{player_out.name} ({out_value:.2f} pts/★) → "
                        f"{player_in.name} ({in_value:.2f} pts/★) = "
                        f"+{value_gain:.2f} pts/★",
                    )
                )

    # Sort by value gain descending
    suggestions.sort(key=lambda s: s.value_gain, reverse=True)
    return suggestions[:top_n]


def get_differential_picks(
    available_players: list[Player],
    player_points: dict[str, float],
    max_ownership: float = 10.0,
    team: Team | None = None,
    top_n: int = 5,
) -> list[PlayerRecommendation]:
    """
    Find high-upside, low-ownership differential picks.

    Differentials are players with low ownership but high expected points,
    offering potential ranking gains when they perform well.

    Args:
        available_players: All available players.
        player_points: Dict mapping player_id to their total points.
        max_ownership: Maximum ownership percentage to consider (default 10%).
        team: Optional current team (to check eligibility).
        top_n: Number of recommendations to return.

    Returns:
        List of PlayerRecommendation for differential picks.
    """
    recommendations: list[PlayerRecommendation] = []

    for player in available_players:
        # Skip if no ownership data or above threshold
        if player.ownership_pct is None:
            continue
        if player.ownership_pct >= max_ownership:
            continue

        # Skip players already in team
        if team and team.get_player(player.id) is not None:
            continue

        # Skip if can't add to team
        if team:
            validation = can_add_player(team, player)
            if not validation.is_valid:
                continue

        total_points = player_points.get(player.id, 0.0)
        if total_points <= 0:
            continue

        # Score combines points and low ownership
        # Higher points + lower ownership = better differential
        ownership_factor = (max_ownership - player.ownership_pct) / max_ownership
        differential_score = total_points * (1 + ownership_factor)

        recommendations.append(
            PlayerRecommendation(
                player=player,
                score=differential_score,
                reason=f"{total_points:.1f} pts, only {player.ownership_pct:.1f}% owned",
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]
