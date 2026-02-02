"""Match and player statistics data models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .player import SelectionStatus


@dataclass
class PlayerMatchStats:
    """
    Statistics for a single player in a single match.

    All stat fields default to 0. Boolean fields default to False.
    """

    player_id: str
    match_id: str
    selection_status: SelectionStatus = SelectionStatus.NOT_SELECTED

    # Attacking stats
    tries: int = 0
    try_assists: int = 0
    conversions: int = 0
    penalty_kicks: int = 0
    drop_goals: int = 0
    metres_carried: int = 0
    defenders_beaten: int = 0
    offloads: int = 0
    fifty_22_kicks: int = 0
    kicks_retained: int = 0
    scrum_wins: int = 0

    # Defensive stats
    tackles: int = 0
    breakdown_steals: int = 0
    lineout_steals: int = 0
    penalties_conceded: int = 0

    # Cards
    yellow_cards: int = 0
    red_cards: int = 0

    # Awards
    player_of_match: bool = False

    def __post_init__(self) -> None:
        """Validate stats are non-negative where required."""
        non_negative_fields = [
            "tries",
            "try_assists",
            "conversions",
            "penalty_kicks",
            "drop_goals",
            "metres_carried",
            "defenders_beaten",
            "offloads",
            "fifty_22_kicks",
            "kicks_retained",
            "scrum_wins",
            "tackles",
            "breakdown_steals",
            "lineout_steals",
            "penalties_conceded",
            "yellow_cards",
            "red_cards",
        ]
        for field_name in non_negative_fields:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def played(self) -> bool:
        """Check if the player participated in the match."""
        return self.selection_status != SelectionStatus.NOT_SELECTED

    @property
    def was_substitute(self) -> bool:
        """Check if the player entered as a substitute."""
        return self.selection_status == SelectionStatus.SUBSTITUTE


@dataclass
class Match:
    """
    Represents a Six Nations match.

    Attributes:
        id: Unique identifier for the match.
        home_team: Home team country code.
        away_team: Away team country code.
        match_date: Date of the match.
        gameweek: The gameweek number (1-5 for Six Nations).
        home_score: Final score for home team.
        away_score: Final score for away team.
    """

    id: str
    home_team: str
    away_team: str
    match_date: date
    gameweek: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate match data."""
        if self.gameweek < 1 or self.gameweek > 5:
            raise ValueError("gameweek must be between 1 and 5")
        if self.home_score is not None and self.home_score < 0:
            raise ValueError("home_score cannot be negative")
        if self.away_score is not None and self.away_score < 0:
            raise ValueError("away_score cannot be negative")

    @property
    def is_completed(self) -> bool:
        """Check if match has been played."""
        return self.home_score is not None and self.away_score is not None
