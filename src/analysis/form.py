"""Form tracker for analyzing player performance trends over recent matches."""

from dataclasses import dataclass
from enum import Enum

from ..models.match import Match, PlayerMatchStats
from ..models.player import Player, Position
from .calculator import calculate_base_points


class FormTrend(Enum):
    """Trend direction for player form."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class PlayerForm:
    """
    Form analysis for a single player.

    Attributes:
        player_id: The player's unique identifier.
        matches_played: Number of matches included in analysis.
        total_points: Total fantasy points over analyzed period.
        average_points: Average points per match.
        trend: Form trend (improving, stable, declining).
        recent_points: List of points per match, most recent first.
    """

    player_id: str
    matches_played: int
    total_points: float
    average_points: float
    trend: FormTrend
    recent_points: list[float]


@dataclass
class FormRecommendation:
    """
    A form-based player recommendation.

    Attributes:
        player: The recommended player.
        form: The player's form analysis.
        score: Recommendation score based on form.
        reason: Human-readable explanation.
    """

    player: Player
    form: PlayerForm
    score: float
    reason: str


def calculate_form_trend(recent_points: list[float]) -> FormTrend:
    """
    Determine form trend from recent match points.

    Compares first half of matches to second half to determine trend.
    Requires at least 2 matches to determine a trend.

    Args:
        recent_points: Points per match, most recent first.

    Returns:
        FormTrend indicating direction of performance.
    """
    if len(recent_points) < 2:
        return FormTrend.STABLE

    midpoint = len(recent_points) // 2
    recent_avg = sum(recent_points[:midpoint]) / midpoint if midpoint > 0 else 0
    older_avg = (
        sum(recent_points[midpoint:]) / (len(recent_points) - midpoint)
        if len(recent_points) > midpoint
        else 0
    )

    # Threshold for significant change (10%)
    threshold = 0.1 * max(recent_avg, older_avg, 1.0)

    if recent_avg > older_avg + threshold:
        return FormTrend.IMPROVING
    elif recent_avg < older_avg - threshold:
        return FormTrend.DECLINING
    return FormTrend.STABLE


def get_player_form(
    player: Player,
    match_stats: list[PlayerMatchStats],
    matches: list[Match],
    recent_matches: int = 3,
) -> PlayerForm:
    """
    Calculate form metrics for a single player.

    Args:
        player: The player to analyze.
        match_stats: List of player's match statistics.
        matches: List of matches (for ordering by date/gameweek).
        recent_matches: Number of recent matches to consider.

    Returns:
        PlayerForm with calculated metrics.
    """
    # Filter to stats for this player where they played
    player_stats = [s for s in match_stats if s.player_id == player.id and s.played]

    if not player_stats:
        return PlayerForm(
            player_id=player.id,
            matches_played=0,
            total_points=0.0,
            average_points=0.0,
            trend=FormTrend.STABLE,
            recent_points=[],
        )

    # Create match lookup for ordering
    match_lookup = {m.id: m for m in matches}

    # Filter out stats with missing match metadata to avoid stale ordering
    player_stats = [s for s in player_stats if s.match_id in match_lookup]
    if not player_stats:
        return PlayerForm(
            player_id=player.id,
            matches_played=0,
            total_points=0.0,
            average_points=0.0,
            trend=FormTrend.STABLE,
            recent_points=[],
        )

    # Sort by match date/gameweek (most recent first)
    player_stats_sorted = sorted(
        player_stats,
        key=lambda s: match_lookup[s.match_id].gameweek,
        reverse=True,
    )

    # Take only recent matches
    recent_stats = player_stats_sorted[:recent_matches]

    # Calculate points for each match
    recent_points = [
        calculate_base_points(stats, player.position) for stats in recent_stats
    ]

    total_points = sum(recent_points)
    matches_played = len(recent_points)
    average_points = total_points / matches_played if matches_played > 0 else 0.0
    trend = calculate_form_trend(recent_points)

    return PlayerForm(
        player_id=player.id,
        matches_played=matches_played,
        total_points=total_points,
        average_points=average_points,
        trend=trend,
        recent_points=recent_points,
    )


def get_form_recommendations(
    players: list[Player],
    match_stats: list[PlayerMatchStats],
    matches: list[Match],
    recent_matches: int = 3,
    min_matches: int = 1,
    top_n: int = 10,
) -> list[FormRecommendation]:
    """
    Get players ranked by current form.

    Args:
        players: All available players.
        match_stats: All player match statistics.
        matches: All matches.
        recent_matches: Number of recent matches to consider for form.
        min_matches: Minimum matches required to be considered.
        top_n: Number of recommendations to return.

    Returns:
        List of FormRecommendation sorted by form score descending.
    """
    recommendations: list[FormRecommendation] = []

    for player in players:
        form = get_player_form(player, match_stats, matches, recent_matches)

        # Skip players without enough match history
        if form.matches_played < min_matches:
            continue

        # Score based on average points with trend bonus
        trend_bonus = {
            FormTrend.IMPROVING: 1.2,
            FormTrend.STABLE: 1.0,
            FormTrend.DECLINING: 0.8,
        }
        score = form.average_points * trend_bonus[form.trend]

        trend_text = {
            FormTrend.IMPROVING: "↑ improving",
            FormTrend.STABLE: "→ stable",
            FormTrend.DECLINING: "↓ declining",
        }

        recommendations.append(
            FormRecommendation(
                player=player,
                form=form,
                score=score,
                reason=f"{form.average_points:.1f} avg pts over {form.matches_played} matches ({trend_text[form.trend]})",
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]


def get_improving_players(
    players: list[Player],
    match_stats: list[PlayerMatchStats],
    matches: list[Match],
    recent_matches: int = 3,
    min_matches: int = 2,
    top_n: int = 5,
) -> list[FormRecommendation]:
    """
    Find players whose form is improving.

    Args:
        players: All available players.
        match_stats: All player match statistics.
        matches: All matches.
        recent_matches: Number of recent matches to consider.
        min_matches: Minimum matches required (need 2+ to determine trend).
        top_n: Number of recommendations to return.

    Returns:
        List of FormRecommendation for improving players.
    """
    recommendations = get_form_recommendations(
        players, match_stats, matches, recent_matches, min_matches, top_n=len(players)
    )

    # Filter to only improving players
    improving = [r for r in recommendations if r.form.trend == FormTrend.IMPROVING]

    return improving[:top_n]


def get_declining_players(
    players: list[Player],
    match_stats: list[PlayerMatchStats],
    matches: list[Match],
    recent_matches: int = 3,
    min_matches: int = 2,
    top_n: int = 5,
) -> list[FormRecommendation]:
    """
    Find players whose form is declining.

    Useful for identifying players to transfer out.

    Args:
        players: All available players.
        match_stats: All player match statistics.
        matches: All matches.
        recent_matches: Number of recent matches to consider.
        min_matches: Minimum matches required (need 2+ to determine trend).
        top_n: Number of recommendations to return.

    Returns:
        List of FormRecommendation for declining players.
    """
    recommendations = get_form_recommendations(
        players, match_stats, matches, recent_matches, min_matches, top_n=len(players)
    )

    # Filter to only declining players
    declining = [r for r in recommendations if r.form.trend == FormTrend.DECLINING]

    return declining[:top_n]
