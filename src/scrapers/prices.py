"""Player price loader from CSV file."""

import csv
import random
from pathlib import Path
from typing import Optional

from ..models import Country, Player, Position

# Default prices by position when no CSV price available
DEFAULT_PRICES = {
    Position.FORWARD: 12.0,
    Position.BACK: 13.0,
}

# Path to player prices CSV
PRICES_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "player_prices.csv"


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

            position = Position.FORWARD if position_str == "forward" else Position.BACK

            # Generate ID from name
            player_id = name.lower().replace(" ", "-").replace(".", "")

            # Generate mock ownership based on price (higher price = higher ownership)
            base_ownership = (price / 16.0) * 30  # 16-star player ~= 30% ownership
            ownership = min(max(base_ownership + random.uniform(-10, 15), 1.0), 80.0)

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
    if seed is not None:
        random.seed(seed)

    points: dict[str, float] = {}

    for player in players:
        # Base points correlate with star value
        base = player.star_value * 2.5

        # Add position-based variance
        if player.position == Position.FORWARD:
            # Forwards have higher floor but lower ceiling
            variance = random.uniform(-3, 8)
        else:
            # Backs have more variance (boom/bust)
            variance = random.uniform(-5, 15)

        # Premium players (high price) tend to score more consistently
        consistency_bonus = (player.star_value - 10) * 0.5 if player.star_value > 10 else 0

        total = max(base + variance + consistency_bonus, 5.0)
        points[player.id] = round(total, 1)

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
