"""Player data model for Six Nations Fantasy."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Country(Enum):
    """Six Nations participating countries."""

    ENGLAND = "England"
    FRANCE = "France"
    IRELAND = "Ireland"
    ITALY = "Italy"
    SCOTLAND = "Scotland"
    WALES = "Wales"


class Position(Enum):
    """Player position category for scoring purposes."""

    FORWARD = "forward"
    BACK = "back"


class SelectionStatus(Enum):
    """Player selection status for a match."""

    STARTER = "starter"
    SUBSTITUTE = "substitute"
    NOT_SELECTED = "not_selected"


@dataclass
class Player:
    """
    Represents a player in Six Nations Fantasy.

    Attributes:
        id: Unique identifier for the player.
        name: Player's full name.
        country: The nation the player represents.
        position: Whether the player is a forward or back.
        star_value: Current price in stars (budget currency).
        ownership_pct: Percentage of fantasy teams owning this player.
    """

    id: str
    name: str
    country: Country
    position: Position
    star_value: float
    ownership_pct: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate player data after initialization."""
        if self.star_value < 0:
            raise ValueError("star_value cannot be negative")
        if self.star_value > 200:
            raise ValueError("star_value cannot exceed total budget (200)")
        if self.ownership_pct is not None:
            if self.ownership_pct < 0 or self.ownership_pct > 100:
                raise ValueError("ownership_pct must be between 0 and 100")

    @property
    def is_forward(self) -> bool:
        """Check if player is a forward."""
        return self.position == Position.FORWARD

    @property
    def is_back(self) -> bool:
        """Check if player is a back."""
        return self.position == Position.BACK
