"""Player price loader from CSV file."""

import csv
from pathlib import Path
from typing import Optional

from ..models import Player, Position

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
