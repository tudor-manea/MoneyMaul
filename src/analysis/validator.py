"""Team validation utilities for fantasy team building."""

from dataclasses import dataclass, field
from typing import Optional

from ..models.player import Country, Player
from ..models.team import (
    MAX_BUDGET,
    MAX_PER_COUNTRY,
    MAX_SQUAD_SIZE,
    MIN_SQUAD_SIZE,
    Team,
    TeamValidationError,
)


@dataclass
class ValidationResult:
    """
    Result of a validation check.

    Attributes:
        is_valid: Whether the validation passed.
        errors: List of validation errors (empty if valid).
        warnings: Non-blocking issues (e.g., incomplete squad).
    """

    is_valid: bool
    errors: list[TeamValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_team(team: Team) -> ValidationResult:
    """
    Validate a team and return detailed results.

    Args:
        team: The team to validate.

    Returns:
        ValidationResult with errors and warnings.
    """
    errors = team.validate()
    warnings: list[str] = []

    # Add warning for incomplete team (points halving applies)
    if not team.is_complete:
        warnings.append(
            f"Incomplete squad ({team.squad_size}/{MIN_SQUAD_SIZE}): "
            "points will be halved"
        )

    # Add warning for missing captain
    if team.captain_id is None and team.squad_size > 0:
        warnings.append("No captain selected: missing 2x multiplier")

    # Add warning for missing supersub
    if team.supersub_id is None and team.squad_size > 0:
        warnings.append("No supersub selected: missing potential 3x multiplier")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def can_add_player(team: Team, player: Player) -> ValidationResult:
    """
    Check if a player can be added to the team.

    Args:
        team: The current team.
        player: The player to potentially add.

    Returns:
        ValidationResult indicating if the add is valid.
    """
    errors: list[TeamValidationError] = []

    # Check if player already in squad
    if team.get_player(player.id) is not None:
        errors.append(
            TeamValidationError(
                code="DUPLICATE_PLAYER",
                message=f"Player {player.name} is already in the squad",
            )
        )
        return ValidationResult(is_valid=False, errors=errors)

    # Check squad size
    if team.squad_size >= MAX_SQUAD_SIZE:
        errors.append(
            TeamValidationError(
                code="SQUAD_FULL",
                message=f"Squad is full ({MAX_SQUAD_SIZE} players)",
            )
        )

    # Check budget
    new_total = team.total_value + player.star_value
    if new_total > MAX_BUDGET:
        errors.append(
            TeamValidationError(
                code="INSUFFICIENT_BUDGET",
                message=f"Adding {player.name} ({player.star_value} stars) "
                f"would exceed budget ({new_total}/{MAX_BUDGET})",
            )
        )

    # Check country limit
    current_count = team.country_counts.get(player.country, 0)
    if current_count >= MAX_PER_COUNTRY:
        errors.append(
            TeamValidationError(
                code="COUNTRY_LIMIT_REACHED",
                message=f"Already have {MAX_PER_COUNTRY} players from "
                f"{player.country.value}",
            )
        )

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def can_remove_player(team: Team, player_id: str) -> ValidationResult:
    """
    Check if a player can be removed from the team.

    Args:
        team: The current team.
        player_id: ID of the player to remove.

    Returns:
        ValidationResult indicating if the removal is valid.
    """
    errors: list[TeamValidationError] = []
    warnings: list[str] = []

    player = team.get_player(player_id)
    if player is None:
        errors.append(
            TeamValidationError(
                code="PLAYER_NOT_FOUND",
                message=f"Player {player_id} is not in the squad",
            )
        )
        return ValidationResult(is_valid=False, errors=errors)

    # Warn if removing captain or supersub
    if team.captain_id == player_id:
        warnings.append(f"Removing captain {player.name}: will need new captain")

    if team.supersub_id == player_id:
        warnings.append(f"Removing supersub {player.name}: will need new supersub")

    return ValidationResult(is_valid=True, errors=[], warnings=warnings)


def can_make_transfer(
    team: Team,
    player_out_id: str,
    player_in: Player,
) -> ValidationResult:
    """
    Check if a transfer (swap) is valid.

    Args:
        team: The current team.
        player_out_id: ID of the player to remove.
        player_in: The player to add.

    Returns:
        ValidationResult indicating if the transfer is valid.
    """
    errors: list[TeamValidationError] = []
    warnings: list[str] = []

    # Check player out exists
    player_out = team.get_player(player_out_id)
    if player_out is None:
        errors.append(
            TeamValidationError(
                code="PLAYER_NOT_FOUND",
                message=f"Player {player_out_id} is not in the squad",
            )
        )
        return ValidationResult(is_valid=False, errors=errors)

    # Check player in not already in squad (unless same player)
    if player_in.id != player_out_id and team.get_player(player_in.id) is not None:
        errors.append(
            TeamValidationError(
                code="DUPLICATE_PLAYER",
                message=f"Player {player_in.name} is already in the squad",
            )
        )
        return ValidationResult(is_valid=False, errors=errors)

    # Calculate new budget
    new_total = team.total_value - player_out.star_value + player_in.star_value
    if new_total > MAX_BUDGET:
        errors.append(
            TeamValidationError(
                code="INSUFFICIENT_BUDGET",
                message=f"Transfer would exceed budget ({new_total}/{MAX_BUDGET})",
            )
        )

    # Check country limit after transfer
    if player_in.country != player_out.country:
        current_count = team.country_counts.get(player_in.country, 0)
        if current_count >= MAX_PER_COUNTRY:
            errors.append(
                TeamValidationError(
                    code="COUNTRY_LIMIT_REACHED",
                    message=f"Already have {MAX_PER_COUNTRY} players from "
                    f"{player_in.country.value}",
                )
            )

    # Warnings for captain/supersub changes
    if team.captain_id == player_out_id:
        warnings.append(
            f"Transferring out captain {player_out.name}: will need new captain"
        )

    if team.supersub_id == player_out_id:
        warnings.append(
            f"Transferring out supersub {player_out.name}: will need new supersub"
        )

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def get_max_player_value(team: Team) -> float:
    """
    Calculate the maximum star value for a new player given current budget.

    Args:
        team: The current team.

    Returns:
        Maximum star value that can be afforded (0 if over budget).
    """
    return max(0.0, team.budget_remaining)


def get_available_slots_for_country(team: Team, country: Country) -> int:
    """
    Get the number of available slots for players from a country.

    Args:
        team: The current team.
        country: The country to check.

    Returns:
        Number of additional players that can be added from this country.
    """
    current_count = team.country_counts.get(country, 0)
    return max(0, MAX_PER_COUNTRY - current_count)


def get_squad_slots_remaining(team: Team) -> int:
    """
    Get the number of squad slots remaining.

    Args:
        team: The current team.

    Returns:
        Number of players that can still be added.
    """
    return max(0, MAX_SQUAD_SIZE - team.squad_size)


def get_transfer_budget(team: Team, player_out: Player) -> float:
    """
    Calculate available budget if a specific player is transferred out.

    Args:
        team: The current team.
        player_out: The player being transferred out.

    Returns:
        Maximum star value for the incoming player (0 if still over budget).
    """
    return max(0.0, team.budget_remaining + player_out.star_value)


def find_affordable_transfers(
    team: Team,
    player_out: Player,
    candidates: list[Player],
) -> list[Player]:
    """
    Find players from a candidate list that could replace a player.

    Args:
        team: The current team.
        player_out: The player being transferred out.
        candidates: List of potential replacement players.

    Returns:
        List of candidates that would be valid transfers.
    """
    valid_candidates: list[Player] = []
    max_value = get_transfer_budget(team, player_out)

    for candidate in candidates:
        # Skip if already in squad
        if team.get_player(candidate.id) is not None:
            continue

        # Skip if too expensive
        if candidate.star_value > max_value:
            continue

        # Skip if country limit reached (and different country)
        if candidate.country != player_out.country:
            if get_available_slots_for_country(team, candidate.country) == 0:
                continue

        valid_candidates.append(candidate)

    return valid_candidates


def auto_select_team(
    players: list[Player],
    player_points: dict[str, float],
) -> Team:
    """
    Automatically select the optimal team within budget/country constraints.

    Uses a two-phase approach:
    1. Greedy selection by expected points to get top performers
    2. Budget optimization to upgrade players with remaining budget

    Args:
        players: All available players.
        player_points: Dict mapping player_id to expected points.

    Returns:
        Team with optimal 15 players selected, maximizing budget usage.
    """
    # Sort players by expected points (highest first)
    sorted_players = sorted(
        [(p, player_points.get(p.id, 0.0)) for p in players if player_points.get(p.id, 0.0) > 0],
        key=lambda x: x[1],
        reverse=True
    )

    team = Team()
    country_counts: dict[Country, int] = {c: 0 for c in Country}
    selected_ids: set[str] = set()

    # Phase 1: Greedy selection by expected points
    for player, _ in sorted_players:
        if team.squad_size >= MIN_SQUAD_SIZE:
            break

        if team.total_value + player.star_value > MAX_BUDGET:
            continue

        if country_counts[player.country] >= MAX_PER_COUNTRY:
            continue

        team.add_player(player)
        country_counts[player.country] += 1
        selected_ids.add(player.id)

    # Phase 2: Try to upgrade players to use more budget
    # Sort team players by points (lowest first) for potential upgrades
    team_by_points = sorted(team.players, key=lambda p: player_points.get(p.id, 0.0))

    for current_player in team_by_points:
        budget_available = team.budget_remaining + current_player.star_value
        current_points = player_points.get(current_player.id, 0.0)

        # Find best upgrade candidate
        best_upgrade = None
        best_upgrade_points = current_points

        for candidate, points in sorted_players:
            if candidate.id in selected_ids:
                continue
            if candidate.star_value > budget_available:
                continue
            if points <= best_upgrade_points:
                continue

            # Check country constraint for different country
            if candidate.country != current_player.country:
                if country_counts[candidate.country] >= MAX_PER_COUNTRY:
                    continue

            best_upgrade = candidate
            best_upgrade_points = points

        # Perform upgrade if found
        if best_upgrade is not None:
            # Update country counts
            country_counts[current_player.country] -= 1
            country_counts[best_upgrade.country] += 1

            # Swap players
            team.remove_player(current_player.id)
            selected_ids.remove(current_player.id)
            team.add_player(best_upgrade)
            selected_ids.add(best_upgrade.id)

    # Phase 3: Fill any remaining slots if we have budget
    if team.squad_size < MIN_SQUAD_SIZE:
        for player, _ in sorted_players:
            if team.squad_size >= MIN_SQUAD_SIZE:
                break
            if player.id in selected_ids:
                continue
            if team.total_value + player.star_value > MAX_BUDGET:
                continue
            if country_counts[player.country] >= MAX_PER_COUNTRY:
                continue

            team.add_player(player)
            country_counts[player.country] += 1
            selected_ids.add(player.id)

    # Set captain as highest expected points player
    if team.players:
        best_captain = max(team.players, key=lambda p: player_points.get(p.id, 0.0))
        team.captain_id = best_captain.id

        # Set supersub as second highest (excluding captain)
        remaining = [p for p in team.players if p.id != best_captain.id]
        if remaining:
            best_supersub = max(remaining, key=lambda p: player_points.get(p.id, 0.0))
            team.supersub_id = best_supersub.id

    return team
