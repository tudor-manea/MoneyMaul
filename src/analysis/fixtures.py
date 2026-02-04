"""Fixture difficulty analysis for Six Nations fantasy."""

from dataclasses import dataclass
from enum import IntEnum

from ..models.match import Match
from ..models.player import Country, Player


class DifficultyRating(IntEnum):
    """Fixture difficulty on a 1-5 scale."""

    VERY_EASY = 1
    EASY = 2
    MEDIUM = 3
    HARD = 4
    VERY_HARD = 5


@dataclass
class TeamStrength:
    """
    Calculated strength metrics for a team.

    Attributes:
        country: The team's country.
        matches_played: Number of matches in calculation.
        points_for: Total points scored.
        points_against: Total points conceded.
        wins: Number of wins.
        point_differential: Points for minus points against.
        strength_score: Normalized strength (0-100).
    """

    country: Country
    matches_played: int
    points_for: int
    points_against: int
    wins: int
    point_differential: int
    strength_score: float


@dataclass
class FixtureDifficulty:
    """
    Difficulty rating for a specific fixture.

    Attributes:
        match: The match being rated.
        home_difficulty: Difficulty for home team.
        away_difficulty: Difficulty for away team.
        home_rating: Numeric rating for home team (1-5).
        away_rating: Numeric rating for away team (1-5).
    """

    match: Match
    home_difficulty: DifficultyRating
    away_difficulty: DifficultyRating
    home_rating: int
    away_rating: int


@dataclass
class FixtureRecommendation:
    """
    A fixture-based player recommendation.

    Attributes:
        player: The recommended player.
        upcoming_difficulty: Average difficulty of upcoming fixtures.
        fixture_details: List of upcoming fixture difficulties.
        score: Recommendation score (lower difficulty = higher score).
        reason: Human-readable explanation.
    """

    player: Player
    upcoming_difficulty: float
    fixture_details: list[tuple[Match, DifficultyRating]]
    score: float
    reason: str


# Country name to enum mapping
COUNTRY_NAME_MAP: dict[str, Country] = {
    "England": Country.ENGLAND,
    "Scotland": Country.SCOTLAND,
    "Ireland": Country.IRELAND,
    "Wales": Country.WALES,
    "France": Country.FRANCE,
    "Italy": Country.ITALY,
}


def calculate_team_strengths(
    matches: list[Match],
) -> dict[Country, TeamStrength]:
    """
    Calculate strength metrics for each team based on match results.

    Only considers completed matches with scores.

    Args:
        matches: List of all matches (completed and upcoming).

    Returns:
        Dict mapping Country to TeamStrength metrics.
    """
    # Initialize accumulators
    stats: dict[Country, dict] = {}
    for country in Country:
        stats[country] = {
            "matches_played": 0,
            "points_for": 0,
            "points_against": 0,
            "wins": 0,
        }

    # Accumulate from completed matches
    for match in matches:
        if not match.is_completed:
            continue

        home_country = COUNTRY_NAME_MAP.get(match.home_team)
        away_country = COUNTRY_NAME_MAP.get(match.away_team)

        if home_country is None or away_country is None:
            continue

        home_score = match.home_score or 0
        away_score = match.away_score or 0

        # Update home team stats
        stats[home_country]["matches_played"] += 1
        stats[home_country]["points_for"] += home_score
        stats[home_country]["points_against"] += away_score
        if home_score > away_score:
            stats[home_country]["wins"] += 1

        # Update away team stats
        stats[away_country]["matches_played"] += 1
        stats[away_country]["points_for"] += away_score
        stats[away_country]["points_against"] += home_score
        if away_score > home_score:
            stats[away_country]["wins"] += 1

    # Calculate strength scores
    strengths: dict[Country, TeamStrength] = {}

    # Check if any matches were played
    total_matches = sum(s["matches_played"] for s in stats.values())
    if total_matches == 0:
        # No matches played, return default 50 strength for all teams
        for country, s in stats.items():
            strengths[country] = TeamStrength(
                country=country,
                matches_played=0,
                points_for=0,
                points_against=0,
                wins=0,
                point_differential=0,
                strength_score=50.0,
            )
        return strengths

    # Find max point differential for normalization
    max_diff = max(
        (s["points_for"] - s["points_against"]) for s in stats.values()
    )
    min_diff = min(
        (s["points_for"] - s["points_against"]) for s in stats.values()
    )
    diff_range = max_diff - min_diff if max_diff != min_diff else 1

    for country, s in stats.items():
        point_diff = s["points_for"] - s["points_against"]
        # Normalize to 0-100 scale
        strength_score = ((point_diff - min_diff) / diff_range) * 100 if diff_range > 0 else 50.0

        strengths[country] = TeamStrength(
            country=country,
            matches_played=s["matches_played"],
            points_for=s["points_for"],
            points_against=s["points_against"],
            wins=s["wins"],
            point_differential=point_diff,
            strength_score=strength_score,
        )

    return strengths


def get_difficulty_rating(opponent_strength: float) -> DifficultyRating:
    """
    Convert opponent strength score to difficulty rating.

    Args:
        opponent_strength: Strength score 0-100.

    Returns:
        DifficultyRating from 1 (very easy) to 5 (very hard).
    """
    if opponent_strength >= 80:
        return DifficultyRating.VERY_HARD
    elif opponent_strength >= 60:
        return DifficultyRating.HARD
    elif opponent_strength >= 40:
        return DifficultyRating.MEDIUM
    elif opponent_strength >= 20:
        return DifficultyRating.EASY
    return DifficultyRating.VERY_EASY


def calculate_fixture_difficulties(
    matches: list[Match],
    team_strengths: dict[Country, TeamStrength] | None = None,
) -> list[FixtureDifficulty]:
    """
    Calculate difficulty ratings for all fixtures.

    Args:
        matches: List of all matches.
        team_strengths: Pre-calculated team strengths (will calculate if None).

    Returns:
        List of FixtureDifficulty for each match.
    """
    if team_strengths is None:
        team_strengths = calculate_team_strengths(matches)

    difficulties: list[FixtureDifficulty] = []

    for match in matches:
        home_country = COUNTRY_NAME_MAP.get(match.home_team)
        away_country = COUNTRY_NAME_MAP.get(match.away_team)

        if home_country is None or away_country is None:
            continue

        # Home team difficulty = opponent strength (away team)
        home_opponent_strength = team_strengths[away_country].strength_score
        away_opponent_strength = team_strengths[home_country].strength_score

        # Home advantage: reduce perceived difficulty by ~10%
        home_difficulty = get_difficulty_rating(home_opponent_strength * 0.9)
        away_difficulty = get_difficulty_rating(away_opponent_strength * 1.1)

        difficulties.append(
            FixtureDifficulty(
                match=match,
                home_difficulty=home_difficulty,
                away_difficulty=away_difficulty,
                home_rating=int(home_difficulty),
                away_rating=int(away_difficulty),
            )
        )

    return difficulties


def get_team_fixture_difficulty(
    country: Country,
    difficulties: list[FixtureDifficulty],
    upcoming_only: bool = True,
) -> list[tuple[Match, DifficultyRating]]:
    """
    Get fixture difficulties for a specific team.

    Args:
        country: The team's country.
        difficulties: Pre-calculated fixture difficulties.
        upcoming_only: If True, only return fixtures without scores.

    Returns:
        List of (Match, DifficultyRating) tuples for the team.
    """
    country_name = country.value.title()
    team_fixtures: list[tuple[Match, DifficultyRating]] = []

    for fd in difficulties:
        if upcoming_only and fd.match.is_completed:
            continue

        if fd.match.home_team == country_name:
            team_fixtures.append((fd.match, fd.home_difficulty))
        elif fd.match.away_team == country_name:
            team_fixtures.append((fd.match, fd.away_difficulty))

    # Sort by gameweek
    team_fixtures.sort(key=lambda x: x[0].gameweek)
    return team_fixtures


def get_fixture_recommendations(
    players: list[Player],
    matches: list[Match],
    gameweeks_ahead: int = 3,
    top_n: int = 10,
) -> list[FixtureRecommendation]:
    """
    Recommend players with favorable upcoming fixtures.

    Args:
        players: All available players.
        matches: All matches.
        gameweeks_ahead: Number of upcoming gameweeks to consider.
        top_n: Number of recommendations to return.

    Returns:
        List of FixtureRecommendation sorted by favorable fixtures.
    """
    # Calculate current gameweek (first incomplete match's gameweek)
    current_gw = 1
    for match in sorted(matches, key=lambda m: m.gameweek):
        if not match.is_completed:
            current_gw = match.gameweek
            break

    # Calculate difficulties
    difficulties = calculate_fixture_difficulties(matches)

    recommendations: list[FixtureRecommendation] = []

    for player in players:
        # Get upcoming fixtures for player's country
        team_fixtures = get_team_fixture_difficulty(
            player.country, difficulties, upcoming_only=True
        )

        # Filter to specified gameweeks ahead
        upcoming = [
            (m, d) for m, d in team_fixtures
            if m.gameweek >= current_gw and m.gameweek < current_gw + gameweeks_ahead
        ]

        if not upcoming:
            continue

        # Calculate average difficulty
        avg_difficulty = sum(int(d) for _, d in upcoming) / len(upcoming)

        # Score: lower difficulty = higher score (invert scale)
        # 1 (very easy) → 5 points, 5 (very hard) → 1 point
        score = 6 - avg_difficulty

        # Format fixture details
        fixture_strs = []
        for match, diff in upcoming:
            opponent = (
                match.away_team if match.home_team == player.country.value.title()
                else match.home_team
            )
            venue = "H" if match.home_team == player.country.value.title() else "A"
            diff_stars = "★" * int(diff)
            fixture_strs.append(f"GW{match.gameweek}: {opponent} ({venue}) {diff_stars}")

        recommendations.append(
            FixtureRecommendation(
                player=player,
                upcoming_difficulty=avg_difficulty,
                fixture_details=upcoming,
                score=score,
                reason=f"Avg difficulty: {avg_difficulty:.1f}/5 | " + ", ".join(fixture_strs),
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]


def get_favorable_captain_picks(
    players: list[Player],
    player_points: dict[str, float],
    matches: list[Match],
    top_n: int = 5,
) -> list[FixtureRecommendation]:
    """
    Recommend captain picks considering both form and fixture difficulty.

    Combines expected points with fixture favorability.

    Args:
        players: All available players.
        player_points: Dict mapping player_id to their expected points.
        matches: All matches.
        top_n: Number of recommendations to return.

    Returns:
        List of FixtureRecommendation for captain selection.
    """
    # Get fixture recommendations (next gameweek only)
    fixture_recs = get_fixture_recommendations(
        players, matches, gameweeks_ahead=1, top_n=len(players)
    )

    # Create lookup for fixture scores
    fixture_scores = {r.player.id: r for r in fixture_recs}

    recommendations: list[FixtureRecommendation] = []

    for player in players:
        base_points = player_points.get(player.id, 0.0)
        if base_points <= 0:
            continue

        fixture_rec = fixture_scores.get(player.id)
        if fixture_rec is None:
            continue

        # Combined score: points * fixture favorability
        # Fixture score is 1-5 (inverted difficulty), normalize to 0.8-1.2 range
        fixture_multiplier = 0.8 + (fixture_rec.score / 5) * 0.4
        combined_score = base_points * fixture_multiplier

        recommendations.append(
            FixtureRecommendation(
                player=player,
                upcoming_difficulty=fixture_rec.upcoming_difficulty,
                fixture_details=fixture_rec.fixture_details,
                score=combined_score,
                reason=f"{base_points:.1f} pts × {fixture_multiplier:.2f} fixture bonus = {combined_score:.1f}",
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations[:top_n]
