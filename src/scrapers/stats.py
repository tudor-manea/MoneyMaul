"""Scraper for match statistics from rugby stats providers."""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..models import Country, Match, PlayerMatchStats, SelectionStatus
from .base import BaseScraper, ParseError, CACHE_DIR


# ESPN Scrum URL (placeholder - actual URL needed)
STATS_BASE_URL = "https://www.espn.co.uk/rugby/scoreboard"


# Mapping from stat field names to PlayerMatchStats attributes
STAT_FIELD_MAP = {
    "tries": "tries",
    "try": "tries",
    "try assists": "try_assists",
    "assists": "try_assists",
    "conversions": "conversions",
    "cons": "conversions",
    "penalties": "penalty_kicks",
    "penalty goals": "penalty_kicks",
    "pens": "penalty_kicks",
    "drop goals": "drop_goals",
    "drops": "drop_goals",
    "metres": "metres_carried",
    "metres carried": "metres_carried",
    "meters": "metres_carried",
    "carries": "metres_carried",
    "defenders beaten": "defenders_beaten",
    "clean breaks": "defenders_beaten",
    "offloads": "offloads",
    "tackles": "tackles",
    "tackles made": "tackles",
    "turnovers won": "breakdown_steals",
    "turnovers": "breakdown_steals",
    "lineout steals": "lineout_steals",
    "penalties conceded": "penalties_conceded",
    "yellow cards": "yellow_cards",
    "yellows": "yellow_cards",
    "red cards": "red_cards",
    "reds": "red_cards",
}


def parse_stat_value(value_str: str) -> int:
    """
    Parse a statistic value string to integer.

    Args:
        value_str: String containing a numeric value.

    Returns:
        Integer value.

    Raises:
        ParseError: If value cannot be parsed.
    """
    try:
        # Handle strings like "5", "5m", "5 metres"
        match = re.search(r"(\d+)", value_str.strip())
        if match:
            return int(match.group(1))
        raise ParseError(f"Cannot parse stat value: {value_str}")
    except (ValueError, AttributeError) as e:
        raise ParseError(f"Cannot parse stat value: {value_str}") from e


class StatsScraper(BaseScraper):
    """
    Scraper for match statistics from rugby stats providers.

    Fetches detailed player statistics for each match including:
    - Attacking stats (tries, assists, kicks, metres, etc.)
    - Defensive stats (tackles, turnovers, etc.)
    - Discipline (cards, penalties conceded)
    """

    def __init__(
        self,
        base_url: str = STATS_BASE_URL,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 24,
    ) -> None:
        """
        Initialize the stats scraper.

        Args:
            base_url: Base URL of the stats website.
            cache_dir: Directory for caching responses.
            cache_ttl_hours: Cache time-to-live in hours.
        """
        super().__init__(
            cache_dir=cache_dir,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_seconds=2.0,  # More conservative rate limiting
        )
        self.base_url = base_url

    def _parse_player_stats_row(
        self, row_html: str, match_id: str
    ) -> Optional[PlayerMatchStats]:
        """
        Parse a player statistics row from the match page.

        Args:
            row_html: HTML string containing player stats.
            match_id: ID of the match.

        Returns:
            PlayerMatchStats object or None if parsing fails.
        """
        soup = self.parse_html(row_html)

        try:
            # Extract player name/ID
            name_elem = soup.select_one(".player-name, .name, td:first-child a")
            if not name_elem:
                return None

            name = name_elem.get_text(strip=True)
            player_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

            # Determine selection status
            status_elem = soup.select_one(".status, [data-status]")
            selection_status = SelectionStatus.STARTER  # Default
            if status_elem:
                status_text = status_elem.get_text(strip=True).lower()
                if "sub" in status_text or "bench" in status_text:
                    selection_status = SelectionStatus.SUBSTITUTE

            # Parse stats
            stats = PlayerMatchStats(
                player_id=player_id,
                match_id=match_id,
                selection_status=selection_status,
            )

            # Find all stat cells
            stat_cells = soup.select("td[data-stat], .stat-value")
            for cell in stat_cells:
                stat_name = cell.get("data-stat", "").lower()
                if not stat_name:
                    # Try to get from header mapping
                    continue

                stat_name_normalized = stat_name.replace("_", " ").replace("-", " ")
                if stat_name_normalized in STAT_FIELD_MAP:
                    field = STAT_FIELD_MAP[stat_name_normalized]
                    value = parse_stat_value(cell.get_text())
                    setattr(stats, field, value)

            return stats

        except (ParseError, ValueError, AttributeError):
            return None

    def scrape_match_stats(
        self, match_id: str, use_cache: bool = True
    ) -> list[PlayerMatchStats]:
        """
        Scrape player statistics for a specific match.

        Args:
            match_id: ID of the match to scrape.
            use_cache: Whether to use cached data if available.

        Returns:
            List of PlayerMatchStats objects.

        Raises:
            FetchError: If fetching data fails.
            ParseError: If parsing data fails.
        """
        url = f"{self.base_url}/match/{match_id}/stats"
        content = self.fetch(url, use_cache=use_cache)

        soup = self.parse_html(content)

        # Find all player stat rows
        player_rows = soup.select(".player-stats-row, .stats-table tbody tr")

        stats = []
        for row in player_rows:
            player_stats = self._parse_player_stats_row(str(row), match_id)
            if player_stats:
                stats.append(player_stats)

        return stats

    def scrape_fixtures(self, use_cache: bool = True) -> list[Match]:
        """
        Scrape fixture list for the tournament.

        Args:
            use_cache: Whether to use cached data if available.

        Returns:
            List of Match objects.

        Raises:
            FetchError: If fetching data fails.
            ParseError: If parsing data fails.
        """
        url = f"{self.base_url}/fixtures"
        content = self.fetch(url, use_cache=use_cache)

        soup = self.parse_html(content)

        # Find all fixture entries
        fixture_elements = soup.select(".fixture, .match-entry, [data-match-id]")

        matches = []
        for elem in fixture_elements:
            try:
                match_id = elem.get("data-match-id", "")
                if not match_id:
                    continue

                home_elem = elem.select_one(".home-team, [data-home]")
                away_elem = elem.select_one(".away-team, [data-away]")
                date_elem = elem.select_one(".match-date, [data-date]")
                gameweek_elem = elem.select_one(".gameweek, [data-gameweek]")

                if not all([home_elem, away_elem, date_elem]):
                    continue

                home_team = home_elem.get_text(strip=True)
                away_team = away_elem.get_text(strip=True)

                # Parse date - try common formats
                date_str = date_elem.get_text(strip=True)
                match_date = date.today()
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
                    try:
                        match_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue

                # Parse gameweek
                gameweek = 1
                if gameweek_elem:
                    gw_match = re.search(r"(\d+)", gameweek_elem.get_text())
                    if gw_match:
                        gameweek = int(gw_match.group(1))

                # Parse scores if available
                home_score = None
                away_score = None
                score_elem = elem.select_one(".score, [data-score]")
                if score_elem:
                    score_text = score_elem.get_text(strip=True)
                    score_match = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
                    if score_match:
                        home_score = int(score_match.group(1))
                        away_score = int(score_match.group(2))

                matches.append(
                    Match(
                        id=match_id,
                        home_team=home_team,
                        away_team=away_team,
                        match_date=match_date,
                        gameweek=gameweek,
                        home_score=home_score,
                        away_score=away_score,
                    )
                )

            except (ParseError, ValueError, AttributeError):
                continue

        return matches

    def scrape(self, match_ids: Optional[list[str]] = None, use_cache: bool = True) -> dict:
        """
        Scrape fixtures and optionally match stats.

        Args:
            match_ids: Optional list of match IDs to scrape stats for.
            use_cache: Whether to use cached data if available.

        Returns:
            Dictionary with 'matches' and 'stats' keys.
        """
        result = {
            "matches": self.scrape_fixtures(use_cache=use_cache),
            "stats": {},
        }

        if match_ids:
            for match_id in match_ids:
                result["stats"][match_id] = self.scrape_match_stats(
                    match_id, use_cache=use_cache
                )

        return result


def create_sample_match() -> Match:
    """
    Create a sample match for testing/development.

    Returns:
        Sample Match object.
    """
    return Match(
        id="2025-six-nations-1",
        home_team="France",
        away_team="Ireland",
        match_date=date(2025, 2, 1),
        gameweek=1,
        home_score=32,
        away_score=19,
    )


def create_sample_stats(match_id: str = "2025-six-nations-1") -> list[PlayerMatchStats]:
    """
    Create sample player match statistics for testing/development.

    Args:
        match_id: ID of the match for these stats.

    Returns:
        List of sample PlayerMatchStats objects.
    """
    return [
        # Antoine Dupont - excellent game
        PlayerMatchStats(
            player_id="antoine-dupont",
            match_id=match_id,
            selection_status=SelectionStatus.STARTER,
            tries=1,
            try_assists=2,
            metres_carried=45,
            defenders_beaten=4,
            offloads=2,
            tackles=8,
            breakdown_steals=1,
            player_of_match=True,
        ),
        # Gregory Alldritt - solid forward performance
        PlayerMatchStats(
            player_id="gregory-alldritt",
            match_id=match_id,
            selection_status=SelectionStatus.STARTER,
            tries=1,
            metres_carried=62,
            defenders_beaten=2,
            offloads=3,
            tackles=14,
            breakdown_steals=2,
            scrum_wins=3,
        ),
        # Tadhg Furlong - tough match
        PlayerMatchStats(
            player_id="tadhg-furlong",
            match_id=match_id,
            selection_status=SelectionStatus.STARTER,
            tries=0,
            metres_carried=28,
            tackles=10,
            scrum_wins=4,
            penalties_conceded=2,
        ),
        # Substitute coming on
        PlayerMatchStats(
            player_id="charles-ollivon",
            match_id=match_id,
            selection_status=SelectionStatus.SUBSTITUTE,
            tries=1,
            metres_carried=15,
            tackles=3,
        ),
    ]
