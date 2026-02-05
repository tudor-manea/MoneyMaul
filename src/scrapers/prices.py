"""Player price loader from CSV file."""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Optional

from ..models import Country, Player, Position
from ..analysis.calculator import calculate_base_points

# Default prices by position when no CSV price available
DEFAULT_PRICES = {
    Position.FORWARD: 12.0,
    Position.BACK: 13.0,
}

# Path to player prices CSV
PRICES_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "player_prices.csv"

# Path to static lineups JSON
LINEUPS_JSON_PATH = Path(__file__).parent.parent.parent / "data" / "lineups_2026.json"

# Country name to enum mapping for lineup loading
LINEUP_COUNTRY_MAP = {
    "England": Country.ENGLAND,
    "Scotland": Country.SCOTLAND,
    "Ireland": Country.IRELAND,
    "Wales": Country.WALES,
    "France": Country.FRANCE,
    "Italy": Country.ITALY,
}


def load_static_lineups(json_path: Optional[Path] = None) -> dict[str, bool]:
    """
    Load 2026 starting lineup status from static JSON file.

    Args:
        json_path: Path to JSON file. Defaults to data/lineups_2026.json.

    Returns:
        Dictionary mapping player name (normalized) to is_starter status.
        Starters map to True, bench players map to False.
    """
    path = json_path or LINEUPS_JSON_PATH
    lineup_status: dict[str, bool] = {}

    if not path.exists():
        return lineup_status

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    teams = data.get("teams", {})
    for team_name, team_data in teams.items():
        # Add starters
        for player in team_data.get("starters", []):
            name = player.get("name", "")
            if name:
                lineup_status[name] = True

        # Add bench players
        for player in team_data.get("bench", []):
            name = player.get("name", "")
            if name:
                lineup_status[name] = False

    return lineup_status


def load_prices_from_csv(csv_path: Optional[Path] = None) -> dict[str, float]:
    """
    Load player prices from CSV file.

    Args:
        csv_path: Path to CSV file. Defaults to data/player_prices.csv.

    Returns:
        Dictionary mapping player name (lowercase) to star value.
        Also includes surname-only keys for fuzzy matching.
    """
    path = csv_path or PRICES_CSV_PATH
    prices: dict[str, float] = {}

    if not path.exists():
        return prices

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            try:
                price = float(row.get("star_value", 0))
                if name and price > 0:
                    # Store full name (lowercase)
                    prices[name.lower()] = price

                    # Also store by surname for fuzzy matching
                    # Handle "F. Surname" format
                    parts = name.split()
                    if len(parts) >= 2:
                        surname = parts[-1].lower()
                        # For multi-part surnames like "Van Der Merwe"
                        if len(parts) > 2 and parts[0].endswith('.'):
                            surname = ' '.join(parts[1:]).lower()
                        # Only add surname if not already present (avoid overwriting)
                        if surname not in prices:
                            prices[surname] = price
            except (ValueError, TypeError):
                continue

    return prices


def apply_prices_to_players(
    players: list[Player],
    prices: Optional[dict[str, float]] = None,
) -> list[Player]:
    """
    Apply prices from CSV to player list.

    Args:
        players: List of Player objects (e.g., from ESPN scraper).
        prices: Price dictionary. If None, loads from CSV.

    Returns:
        List of Player objects with updated prices.
    """
    if prices is None:
        prices = load_prices_from_csv()

    updated_players = []
    for player in players:
        price = None

        # Try to find price by full name (case-insensitive)
        name_key = player.name.lower()
        if name_key in prices:
            price = prices[name_key]
        else:
            # Try matching by surname only
            # ESPN names are like "Antoine Dupont", CSV has "A. Dupont"
            name_parts = player.name.split()
            if len(name_parts) >= 2:
                surname = name_parts[-1].lower()
                if surname in prices:
                    price = prices[surname]
                else:
                    # Try multi-part surname (e.g., "Van Der Merwe")
                    for i in range(1, len(name_parts)):
                        multi_surname = ' '.join(name_parts[i:]).lower()
                        if multi_surname in prices:
                            price = prices[multi_surname]
                            break

        # Fall back to default price based on position
        if price is None:
            price = DEFAULT_PRICES.get(player.position, 12.0)

        # Create new player with updated price
        updated_players.append(
            Player(
                id=player.id,
                name=player.name,
                country=player.country,
                position=player.position,
                star_value=price,
                ownership_pct=player.ownership_pct,
            )
        )

    return updated_players


def load_all_players_from_csv(csv_path: Optional[Path] = None) -> list[Player]:
    """
    Load all players directly from the prices CSV file.

    This creates Player objects from the CSV data, generating IDs
    and mock ownership percentages.

    Args:
        csv_path: Path to CSV file. Defaults to data/player_prices.csv.

    Returns:
        List of Player objects with all data from CSV.
    """
    path = csv_path or PRICES_CSV_PATH
    players: list[Player] = []
    seen_ids: set[str] = set()

    if not path.exists():
        return players

    # Country name mapping
    country_map = {
        "england": Country.ENGLAND,
        "scotland": Country.SCOTLAND,
        "ireland": Country.IRELAND,
        "wales": Country.WALES,
        "france": Country.FRANCE,
        "italy": Country.ITALY,
    }

    # Use local RNG for ownership generation to avoid global state mutation
    rng = random.Random(42)

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            country_str = row.get("country", "").strip().lower()
            position_str = row.get("position", "").strip().lower()

            try:
                price = float(row.get("star_value", 0))
            except (ValueError, TypeError):
                continue

            if not name or price <= 0:
                continue

            country = country_map.get(country_str)
            if country is None:
                continue

            # Validate position explicitly - skip invalid rows
            if position_str == "forward":
                position = Position.FORWARD
            elif position_str == "back":
                position = Position.BACK
            else:
                continue

            # Generate unique ID with country prefix to avoid collisions
            name_slug = name.lower().replace(" ", "-").replace(".", "")
            base_id = f"{country.value.lower()}-{name_slug}"
            player_id = base_id
            if player_id in seen_ids:
                suffix = 2
                while f"{base_id}-{suffix}" in seen_ids:
                    suffix += 1
                player_id = f"{base_id}-{suffix}"
            seen_ids.add(player_id)

            # Generate mock ownership based on price (higher price = higher ownership)
            base_ownership = (price / 16.0) * 30  # 16-star player ~= 30% ownership
            ownership = min(max(base_ownership + rng.uniform(-10, 15), 1.0), 80.0)

            players.append(
                Player(
                    id=player_id,
                    name=name,
                    country=country,
                    position=position,
                    star_value=price,
                    ownership_pct=round(ownership, 1),
                )
            )

    return players


def generate_mock_player_points(
    players: list[Player],
    seed: Optional[int] = None,
) -> dict[str, float]:
    """
    Generate realistic mock points for players.

    Points are based on star value with position-based variance
    to create differentiated recommendations.

    Args:
        players: List of Player objects.
        seed: Random seed for reproducibility.

    Returns:
        Dictionary mapping player_id to expected points.
    """
    # Use local RNG to avoid global state mutation
    rng = random.Random(seed)

    points: dict[str, float] = {}

    for player in players:
        # Base points correlate with star value
        base = player.star_value * 2.5

        # Add position-based variance
        if player.position == Position.FORWARD:
            # Forwards have higher floor but lower ceiling
            variance = rng.uniform(-3, 8)
        else:
            # Backs have more variance (boom/bust)
            variance = rng.uniform(-5, 15)

        # Premium players (high price) tend to score more consistently
        consistency_bonus = (player.star_value - 10) * 0.5 if player.star_value > 10 else 0

        total = max(base + variance + consistency_bonus, 5.0)
        points[player.id] = round(total, 1)

    return points


def _calculate_scoring_only_points(
    stats: "PlayerMatchStats", position: Position
) -> float:
    """
    Calculate fantasy points from scoring events only.

    Used for calibrating Autumn International play-by-play data (which only has
    scoring events) against full Six Nations data.

    Args:
        stats: Player match statistics.
        position: Player position (forward/back).

    Returns:
        Points from tries, conversions, penalties, drop goals, and cards only.
    """
    from ..analysis.calculator import (
        POINTS_CONVERSION,
        POINTS_DROP_GOAL,
        POINTS_PENALTY_KICK,
        POINTS_RED_CARD,
        POINTS_TRY_BACK,
        POINTS_TRY_FORWARD,
        POINTS_YELLOW_CARD,
    )

    points = 0.0
    try_points = POINTS_TRY_FORWARD if position == Position.FORWARD else POINTS_TRY_BACK
    points += stats.tries * try_points
    points += stats.conversions * POINTS_CONVERSION
    points += stats.penalty_kicks * POINTS_PENALTY_KICK
    points += stats.drop_goals * POINTS_DROP_GOAL
    points += stats.yellow_cards * POINTS_YELLOW_CARD
    points += stats.red_cards * POINTS_RED_CARD
    return points


def calculate_form_based_points(
    players: list[Player],
    form_year: int = 2025,
    lineup_year: int = 2026,
    use_static_lineups: bool = True,
    include_autumn: bool = True,
    autumn_weight: float = 0.6,
) -> dict[str, float]:
    """
    Calculate expected points based on real form data from previous tournament.

    Uses actual match statistics from the form_year tournament to calculate
    fantasy points, then applies lineup bonuses from the current year.
    Optionally incorporates Autumn International data via calibration ratios.

    Args:
        players: List of Player objects (from CSV).
        form_year: Year to pull form data from (default: 2025).
        lineup_year: Year to check starting lineups (default: 2026).
        use_static_lineups: If True, use static JSON lineups as primary source.
        include_autumn: If True, incorporate Autumn International stats.
        autumn_weight: Weight for Autumn data when blending (0.0-1.0).

    Returns:
        Dictionary mapping player_id to expected points.
    """
    # Import here to avoid circular imports
    from .espn import ESPNScraper

    scraper = ESPNScraper()

    # Get form data from previous tournament
    form_data = scraper.scrape_form_data(year=form_year, use_cache=True)

    # Get current starting lineups - prefer static JSON if available
    lineup_status: dict[str, bool] = {}
    if use_static_lineups:
        lineup_status = load_static_lineups()

    # Fall back to ESPN if no static lineups or very few players
    if len(lineup_status) < 50:
        espn_lineups = scraper.scrape_starting_lineups(year=lineup_year, use_cache=True)
        # Merge ESPN data (don't overwrite static data)
        for name, is_starter in espn_lineups.items():
            if name not in lineup_status:
                lineup_status[name] = is_starter

    # Build surname+country lookup from CSV players
    # Key: (surname_lower, country) -> list of (player_id, full_name, star_value)
    csv_lookup: dict[tuple[str, Country], list[tuple[str, str, float]]] = defaultdict(list)
    for player in players:
        name_parts = player.name.split()
        if name_parts:
            # Get last part as surname
            surname = name_parts[-1].lower()
            csv_lookup[(surname, player.country)].append(
                (player.id, player.name, player.star_value)
            )

    # Aggregate Six Nations fantasy points per player
    # Key: (espn_name, country) -> list of (full_points, scoring_only_points)
    sn_full_per_match: dict[tuple[str, Country], list[float]] = defaultdict(list)
    sn_scoring_per_match: dict[tuple[str, Country], list[float]] = defaultdict(list)
    player_positions: dict[tuple[str, Country], Position] = {}

    for espn_name, country, position, stats in form_data:
        key = (espn_name, country)
        full_pts = calculate_base_points(stats, position)
        scoring_pts = _calculate_scoring_only_points(stats, position)
        sn_full_per_match[key].append(full_pts)
        sn_scoring_per_match[key].append(scoring_pts)
        player_positions[key] = position

    # Fetch Autumn International data if requested
    autumn_scoring_per_match: dict[tuple[str, Country], list[float]] = defaultdict(list)
    autumn_positions: dict[tuple[str, Country], Position] = {}
    if include_autumn:
        try:
            autumn_data = scraper.scrape_autumn_form_data(
                year=form_year, use_cache=True
            )
            for espn_name, country, position, stats in autumn_data:
                key = (espn_name, country)
                scoring_pts = _calculate_scoring_only_points(stats, position)
                autumn_scoring_per_match[key].append(scoring_pts)
                autumn_positions[key] = position
        except Exception:
            # Graceful fallback: proceed with Six Nations data only
            pass

    # Compute position-average calibration ratios from Six Nations data
    # ratio = full_points / scoring_only_points (per position)
    pos_ratio_sums: dict[Position, float] = defaultdict(float)
    pos_ratio_counts: dict[Position, int] = defaultdict(int)

    for key, full_list in sn_full_per_match.items():
        scoring_list = sn_scoring_per_match[key]
        position = player_positions[key]

        sn_full_avg = sum(full_list) / len(full_list)
        sn_scoring_avg = sum(scoring_list) / len(scoring_list)

        if sn_scoring_avg >= 1.0:
            ratio = sn_full_avg / sn_scoring_avg
            pos_ratio_sums[position] += ratio
            pos_ratio_counts[position] += 1

    pos_avg_ratios: dict[Position, float] = {}
    for pos in Position:
        if pos_ratio_counts.get(pos, 0) > 0:
            pos_avg_ratios[pos] = pos_ratio_sums[pos] / pos_ratio_counts[pos]
        else:
            pos_avg_ratios[pos] = 2.0  # Sensible default

    # All unique player keys from both data sources
    all_player_keys = set(sn_full_per_match.keys()) | set(autumn_scoring_per_match.keys())

    # Match ESPN players to CSV players and calculate form scores
    points: dict[str, float] = {}
    matched_csv_ids: set[str] = set()

    for key in all_player_keys:
        espn_name, country = key

        has_sn = key in sn_full_per_match
        has_autumn = key in autumn_scoring_per_match
        position = player_positions.get(key) or autumn_positions.get(key)
        if position is None:
            continue

        # Calculate per-source averages
        sn_full_avg = 0.0
        sn_scoring_avg = 0.0
        autumn_scoring_avg = 0.0

        if has_sn:
            sn_full_avg = sum(sn_full_per_match[key]) / len(sn_full_per_match[key])
            sn_scoring_avg = sum(sn_scoring_per_match[key]) / len(sn_scoring_per_match[key])

        if has_autumn:
            autumn_scoring_avg = (
                sum(autumn_scoring_per_match[key]) / len(autumn_scoring_per_match[key])
            )

        # Compute blended average points
        if has_sn and has_autumn and include_autumn:
            # Both sources: use personal calibration ratio
            if sn_scoring_avg >= 1.0:
                personal_ratio = sn_full_avg / sn_scoring_avg
            else:
                personal_ratio = pos_avg_ratios[position]
            autumn_estimated = autumn_scoring_avg * personal_ratio
            avg_points = (1 - autumn_weight) * sn_full_avg + autumn_weight * autumn_estimated
        elif has_sn:
            # Six Nations only
            avg_points = sn_full_avg
        elif has_autumn and include_autumn:
            # Autumn only (new caps): use position-average ratio
            avg_points = autumn_scoring_avg * pos_avg_ratios[position]
        else:
            continue

        # Try to match to CSV player by surname + country
        espn_name_parts = espn_name.split()
        if not espn_name_parts:
            continue

        espn_surname = espn_name_parts[-1].lower()
        csv_candidates = csv_lookup.get((espn_surname, country), [])

        matched_player_id = None
        if len(csv_candidates) == 1:
            # Single match - use it
            matched_player_id = csv_candidates[0][0]
        elif len(csv_candidates) > 1:
            # Multiple matches - try to match by full first name
            espn_first = espn_name_parts[0].lower() if len(espn_name_parts) > 1 else ""
            for player_id, full_name, _ in csv_candidates:
                csv_parts = full_name.split()
                # CSV names like "A. Dupont" - check if first initial matches
                csv_first = csv_parts[0].lower() if csv_parts else ""
                if csv_first and espn_first:
                    if csv_first.startswith(espn_first[0]) or espn_first.startswith(csv_first[0]):
                        matched_player_id = player_id
                        break
            # If still no match, just take the first candidate
            if matched_player_id is None:
                matched_player_id = csv_candidates[0][0]

        if matched_player_id:
            # Apply lineup bonus
            is_starter = lineup_status.get(espn_name, False)
            in_squad = espn_name in lineup_status

            if is_starter:
                # Starter bonus: +20%
                final_points = avg_points * 1.2
            elif in_squad:
                # In squad but not starting: no modifier
                final_points = avg_points
            else:
                # Not in 2026 squad: -30%
                final_points = avg_points * 0.7

            points[matched_player_id] = round(final_points, 1)
            matched_csv_ids.add(matched_player_id)

    # Fallback for unmatched CSV players: star_value * 1.5 (below avg form)
    for player in players:
        if player.id not in matched_csv_ids:
            # Check if they're in the 2026 lineup by trying surname match
            name_parts = player.name.split()
            surname = name_parts[-1] if name_parts else player.name

            # Search lineup_status for matching surname
            is_in_lineup = False
            for lineup_name in lineup_status:
                if surname.lower() in lineup_name.lower():
                    is_in_lineup = True
                    break

            if is_in_lineup:
                # In 2026 squad but no 2025 form data - moderate estimate
                points[player.id] = round(player.star_value * 2.0, 1)
            else:
                # Not in squad and no form data - low estimate
                points[player.id] = round(player.star_value * 1.5, 1)

    return points


def generate_prices_template(players: list[Player], csv_path: Optional[Path] = None) -> Path:
    """
    Generate a CSV template for player prices.

    Args:
        players: List of Player objects to include.
        csv_path: Path for output CSV. Defaults to data/player_prices.csv.

    Returns:
        Path to generated CSV file.
    """
    path = csv_path or PRICES_CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by country then name
    sorted_players = sorted(players, key=lambda p: (p.country.value, p.name))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "country", "position", "star_value"])
        for player in sorted_players:
            writer.writerow([
                player.name,
                player.country.value,
                player.position.value,
                player.star_value,
            ])

    return path
