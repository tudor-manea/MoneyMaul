"""Scraper for official Six Nations Fantasy game data."""

import re
from pathlib import Path
from typing import Optional

from ..models import Country, Player, Position
from .base import BaseScraper, ParseError, CACHE_DIR


# Six Nations Fantasy website URL (placeholder - actual URL needed)
FANTASY_BASE_URL = "https://fantasy.sixnationsrugby.com"


# Position mapping for Six Nations players
# Jersey numbers 1-8 are forwards, 9-15 are backs
FORWARD_POSITIONS = {
    "Loosehead Prop",
    "Hooker",
    "Tighthead Prop",
    "Lock",
    "Second Row",
    "Blindside Flanker",
    "Openside Flanker",
    "Flanker",
    "Number 8",
    "No. 8",
    "Prop",
}

BACK_POSITIONS = {
    "Scrum-half",
    "Scrum Half",
    "Fly-half",
    "Fly Half",
    "Inside Centre",
    "Outside Centre",
    "Centre",
    "Wing",
    "Winger",
    "Full-back",
    "Fullback",
    "Full Back",
}


# Country name variations mapping
COUNTRY_MAP = {
    "england": Country.ENGLAND,
    "eng": Country.ENGLAND,
    "france": Country.FRANCE,
    "fra": Country.FRANCE,
    "ireland": Country.IRELAND,
    "ire": Country.IRELAND,
    "italy": Country.ITALY,
    "ita": Country.ITALY,
    "scotland": Country.SCOTLAND,
    "sco": Country.SCOTLAND,
    "wales": Country.WALES,
    "wal": Country.WALES,
}


def parse_country(country_str: str) -> Country:
    """
    Parse a country string to Country enum.

    Args:
        country_str: Country name or code.

    Returns:
        Country enum value.

    Raises:
        ParseError: If country cannot be parsed.
    """
    normalized = country_str.lower().strip()
    if normalized in COUNTRY_MAP:
        return COUNTRY_MAP[normalized]
    raise ParseError(f"Unknown country: {country_str}")


def parse_position(position_str: str) -> Position:
    """
    Parse a position string to Position enum.

    Args:
        position_str: Position name.

    Returns:
        Position enum value (FORWARD or BACK).

    Raises:
        ParseError: If position cannot be parsed.
    """
    normalized = position_str.strip()
    if normalized in FORWARD_POSITIONS:
        return Position.FORWARD
    if normalized in BACK_POSITIONS:
        return Position.BACK

    # Try to infer from common patterns
    lower = normalized.lower()
    if any(term in lower for term in ["prop", "hooker", "lock", "flanker", "8"]):
        return Position.FORWARD
    if any(term in lower for term in ["half", "centre", "center", "wing", "back"]):
        return Position.BACK

    raise ParseError(f"Unknown position: {position_str}")


class FantasyScraper(BaseScraper):
    """
    Scraper for Six Nations Fantasy game data.

    Fetches player information including:
    - Player names and IDs
    - Country/team
    - Position (forward/back)
    - Star value (price)
    - Ownership percentage
    """

    def __init__(
        self,
        base_url: str = FANTASY_BASE_URL,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 1,
    ) -> None:
        """
        Initialize the fantasy scraper.

        Args:
            base_url: Base URL of the fantasy game website.
            cache_dir: Directory for caching responses.
            cache_ttl_hours: Cache time-to-live in hours.
        """
        super().__init__(
            cache_dir=cache_dir,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_seconds=1.0,
        )
        self.base_url = base_url

    def _parse_player_card(self, card_html: str) -> Optional[Player]:
        """
        Parse a player card HTML element.

        Args:
            card_html: HTML string containing player information.

        Returns:
            Player object or None if parsing fails.
        """
        soup = self.parse_html(card_html)

        try:
            # These selectors are placeholders - actual selectors depend on
            # the structure of the Six Nations Fantasy website
            name_elem = soup.select_one(".player-name, .name, [data-player-name]")
            country_elem = soup.select_one(".player-team, .team, [data-team]")
            position_elem = soup.select_one(".player-position, .position, [data-position]")
            price_elem = soup.select_one(".player-price, .price, [data-price]")
            ownership_elem = soup.select_one(".player-ownership, .ownership, [data-ownership]")

            if not all([name_elem, country_elem, position_elem, price_elem]):
                return None

            # Extract text content
            name = name_elem.get_text(strip=True)
            country = parse_country(country_elem.get_text(strip=True))
            position = parse_position(position_elem.get_text(strip=True))

            # Parse price (extract number from string like "12.5" or "12.5 stars")
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"(\d+\.?\d*)", price_text)
            if not price_match:
                return None
            star_value = float(price_match.group(1))

            # Parse ownership (optional)
            ownership_pct = None
            if ownership_elem:
                ownership_text = ownership_elem.get_text(strip=True)
                ownership_match = re.search(r"(\d+\.?\d*)", ownership_text)
                if ownership_match:
                    ownership_pct = float(ownership_match.group(1))

            # Generate ID from name (slugified)
            player_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

            return Player(
                id=player_id,
                name=name,
                country=country,
                position=position,
                star_value=star_value,
                ownership_pct=ownership_pct,
            )

        except (ParseError, ValueError, AttributeError):
            return None

    def scrape_players(self, use_cache: bool = True) -> list[Player]:
        """
        Scrape all players from the fantasy game.

        Args:
            use_cache: Whether to use cached data if available.

        Returns:
            List of Player objects.

        Raises:
            FetchError: If fetching data fails.
            ParseError: If parsing data fails.
        """
        url = f"{self.base_url}/api/players"
        content = self.fetch(url, use_cache=use_cache)

        soup = self.parse_html(content)

        # Find all player cards/entries
        # These selectors are placeholders - actual selectors depend on
        # the structure of the Six Nations Fantasy website
        player_elements = soup.select(".player-card, .player-item, [data-player-id]")

        players = []
        for elem in player_elements:
            player = self._parse_player_card(str(elem))
            if player:
                players.append(player)

        return players

    def scrape(self, use_cache: bool = True) -> list[Player]:
        """
        Scrape all player data.

        Args:
            use_cache: Whether to use cached data if available.

        Returns:
            List of Player objects.
        """
        return self.scrape_players(use_cache=use_cache)


def create_sample_players() -> list[Player]:
    """
    Create sample player data for testing/development.

    Returns:
        List of sample Player objects representing a realistic squad.
    """
    return [
        # England
        Player(
            id="marcus-smith",
            name="Marcus Smith",
            country=Country.ENGLAND,
            position=Position.BACK,
            star_value=14.5,
            ownership_pct=45.2,
        ),
        Player(
            id="maro-itoje",
            name="Maro Itoje",
            country=Country.ENGLAND,
            position=Position.FORWARD,
            star_value=13.0,
            ownership_pct=38.5,
        ),
        # France
        Player(
            id="antoine-dupont",
            name="Antoine Dupont",
            country=Country.FRANCE,
            position=Position.BACK,
            star_value=16.0,
            ownership_pct=72.3,
        ),
        Player(
            id="gregory-alldritt",
            name="Gregory Alldritt",
            country=Country.FRANCE,
            position=Position.FORWARD,
            star_value=14.0,
            ownership_pct=41.8,
        ),
        # Ireland
        Player(
            id="johnny-sexton",
            name="Johnny Sexton",
            country=Country.IRELAND,
            position=Position.BACK,
            star_value=12.0,
            ownership_pct=28.1,
        ),
        Player(
            id="tadhg-furlong",
            name="Tadhg Furlong",
            country=Country.IRELAND,
            position=Position.FORWARD,
            star_value=13.5,
            ownership_pct=35.7,
        ),
        # Italy
        Player(
            id="ange-capuozzo",
            name="Ange Capuozzo",
            country=Country.ITALY,
            position=Position.BACK,
            star_value=11.0,
            ownership_pct=18.9,
        ),
        Player(
            id="michele-lamaro",
            name="Michele Lamaro",
            country=Country.ITALY,
            position=Position.FORWARD,
            star_value=10.5,
            ownership_pct=15.2,
        ),
        # Scotland
        Player(
            id="finn-russell",
            name="Finn Russell",
            country=Country.SCOTLAND,
            position=Position.BACK,
            star_value=14.0,
            ownership_pct=52.1,
        ),
        Player(
            id="rory-darge",
            name="Rory Darge",
            country=Country.SCOTLAND,
            position=Position.FORWARD,
            star_value=12.0,
            ownership_pct=29.4,
        ),
        # Wales
        Player(
            id="louis-rees-zammit",
            name="Louis Rees-Zammit",
            country=Country.WALES,
            position=Position.BACK,
            star_value=13.0,
            ownership_pct=44.6,
        ),
        Player(
            id="jac-morgan",
            name="Jac Morgan",
            country=Country.WALES,
            position=Position.FORWARD,
            star_value=11.5,
            ownership_pct=22.8,
        ),
    ]
