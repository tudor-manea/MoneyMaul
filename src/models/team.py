"""Fantasy team data model with validation."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .player import Country, Player


# Game constants
MAX_BUDGET = 200
MAX_PER_COUNTRY = 4
MIN_SQUAD_SIZE = 15
MAX_SQUAD_SIZE = 16


@dataclass
class TeamValidationError:
    """Represents a validation error for a fantasy team."""

    code: str
    message: str


@dataclass
class Team:
    """
    Represents a fantasy team selection.

    Attributes:
        players: List of players in the squad.
        captain_id: ID of the captain (2x points).
        supersub_id: ID of the supersub (3x if sub, 0.5x otherwise).
    """

    players: list[Player] = field(default_factory=list)
    captain_id: Optional[str] = None
    supersub_id: Optional[str] = None

    @property
    def total_value(self) -> float:
        """Calculate total star value of the squad."""
        return sum(p.star_value for p in self.players)

    @property
    def budget_remaining(self) -> float:
        """Calculate remaining budget."""
        return MAX_BUDGET - self.total_value

    @property
    def squad_size(self) -> int:
        """Return number of players in squad."""
        return len(self.players)

    @property
    def country_counts(self) -> dict[Country, int]:
        """Count players per country."""
        return dict(Counter(p.country for p in self.players))

    @property
    def captain(self) -> Optional[Player]:
        """Get the captain player."""
        if self.captain_id is None:
            return None
        return next((p for p in self.players if p.id == self.captain_id), None)

    @property
    def supersub(self) -> Optional[Player]:
        """Get the supersub player."""
        if self.supersub_id is None:
            return None
        return next((p for p in self.players if p.id == self.supersub_id), None)

    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID."""
        return next((p for p in self.players if p.id == player_id), None)

    def add_player(self, player: Player) -> None:
        """Add a player to the squad."""
        if self.get_player(player.id) is not None:
            raise ValueError(f"Player {player.id} already in squad")
        self.players.append(player)

    def remove_player(self, player_id: str) -> None:
        """Remove a player from the squad."""
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player {player_id} not in squad")
        self.players.remove(player)
        if self.captain_id == player_id:
            self.captain_id = None
        if self.supersub_id == player_id:
            self.supersub_id = None

    def set_captain(self, player_id: str) -> None:
        """Set the captain."""
        if self.get_player(player_id) is None:
            raise ValueError(f"Player {player_id} not in squad")
        self.captain_id = player_id

    def set_supersub(self, player_id: str) -> None:
        """Set the supersub."""
        if self.get_player(player_id) is None:
            raise ValueError(f"Player {player_id} not in squad")
        if self.captain_id == player_id:
            raise ValueError("Captain cannot also be supersub")
        self.supersub_id = player_id

    def validate(self) -> list[TeamValidationError]:
        """
        Validate the team against game rules.

        Returns:
            List of validation errors. Empty list if valid.
        """
        errors: list[TeamValidationError] = []

        # Budget check
        if self.total_value > MAX_BUDGET:
            errors.append(
                TeamValidationError(
                    code="OVER_BUDGET",
                    message=f"Team value ({self.total_value}) exceeds budget ({MAX_BUDGET})",
                )
            )

        # Squad size check
        if self.squad_size < MIN_SQUAD_SIZE:
            errors.append(
                TeamValidationError(
                    code="UNDER_MIN_SQUAD",
                    message=f"Squad size ({self.squad_size}) below minimum ({MIN_SQUAD_SIZE})",
                )
            )
        elif self.squad_size > MAX_SQUAD_SIZE:
            errors.append(
                TeamValidationError(
                    code="OVER_MAX_SQUAD",
                    message=f"Squad size ({self.squad_size}) exceeds maximum ({MAX_SQUAD_SIZE})",
                )
            )

        # Country limit check
        for country, count in self.country_counts.items():
            if count > MAX_PER_COUNTRY:
                errors.append(
                    TeamValidationError(
                        code="COUNTRY_LIMIT",
                        message=f"Too many players from {country.value} ({count}/{MAX_PER_COUNTRY})",
                    )
                )

        # Captain validation
        if self.captain_id is not None and self.captain is None:
            errors.append(
                TeamValidationError(
                    code="INVALID_CAPTAIN",
                    message=f"Captain {self.captain_id} not in squad",
                )
            )

        # Supersub validation
        if self.supersub_id is not None:
            if self.supersub is None:
                errors.append(
                    TeamValidationError(
                        code="INVALID_SUPERSUB",
                        message=f"Supersub {self.supersub_id} not in squad",
                    )
                )
            elif self.supersub_id == self.captain_id:
                errors.append(
                    TeamValidationError(
                        code="CAPTAIN_IS_SUPERSUB",
                        message="Captain cannot also be supersub",
                    )
                )

        return errors

    @property
    def is_valid(self) -> bool:
        """Check if team passes all validation rules."""
        return len(self.validate()) == 0

    @property
    def is_complete(self) -> bool:
        """Check if team has minimum required players."""
        return self.squad_size >= MIN_SQUAD_SIZE
