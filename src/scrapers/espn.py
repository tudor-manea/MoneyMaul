"""ESPN API scraper for Six Nations rugby data."""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..models import Country, Match, Player, PlayerMatchStats, Position, SelectionStatus
from .base import BaseScraper, ParseError, CACHE_DIR


# ESPN API endpoint for Six Nations (league ID: 180659)
ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports/rugby/180659"

# World Rugby Rankings API
WORLD_RUGBY_RANKINGS_URL = "https://api.wr-rims-prod.pulselive.com/rugby/v3/rankings/mru"

# ESPN roster stat name → PlayerMatchStats field mapping
# Stats come as a list of {name, value, displayValue} objects
ESPN_STAT_MAP: dict[str, str] = {
    "tries": "tries",
    "tryAssists": "try_assists",
    "conversionGoals": "conversions",
    "penaltyGoals": "penalty_kicks",
    "dropGoalsConverted": "drop_goals",
    "metres": "metres_carried",
    "defendersBeaten": "defenders_beaten",
    "offload": "offloads",
    "tackles": "tackles",
    "penaltiesConceded": "penalties_conceded",
    "yellowCards": "yellow_cards",
    "redCards": "red_cards",
    "rucksWon": "breakdown_steals",
    "lineoutsWon": "lineout_steals",
}

# World Rugby team name → Country mapping
WORLD_RUGBY_TEAM_MAP: dict[str, Country] = {
    "England": Country.ENGLAND,
    "Scotland": Country.SCOTLAND,
    "Ireland": Country.IRELAND,
    "Wales": Country.WALES,
    "France": Country.FRANCE,
    "Italy": Country.ITALY,
}

# ESPN team ID to Country mapping
ESPN_TEAM_MAP = {
    1: Country.ENGLAND,
    2: Country.SCOTLAND,
    3: Country.IRELAND,
    4: Country.WALES,
    9: Country.FRANCE,
    20: Country.ITALY,
}

# Country to ESPN team ID (reverse mapping)
COUNTRY_TO_ESPN_ID = {v: k for k, v in ESPN_TEAM_MAP.items()}

# Jersey number to position mapping (1-8 forwards, 9-15 backs)
FORWARD_JERSEYS = {1, 2, 3, 4, 5, 6, 7, 8}
BACK_JERSEYS = {9, 10, 11, 12, 13, 14, 15}


def parse_espn_date(date_str: str) -> date:
    """
    Parse ESPN date string to date object.

    Args:
        date_str: ISO format date string from ESPN API.

    Returns:
        date object.
    """
    # ESPN returns dates like "2026-02-01T15:15Z"
    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()


def jersey_to_position(jersey: int) -> Position:
    """
    Determine position from jersey number.

    Args:
        jersey: Jersey number (1-23).

    Returns:
        Position enum (FORWARD or BACK).

    Raises:
        ValueError: If jersey number is not in valid range (1-23).
    """
    if not isinstance(jersey, int) or jersey < 1 or jersey > 23:
        raise ValueError(f"Invalid jersey number: {jersey}. Must be 1-23.")

    if jersey in FORWARD_JERSEYS:
        return Position.FORWARD
    if jersey in BACK_JERSEYS:
        return Position.BACK
    # Bench players (16-23): 16-20 typically forwards, 21-23 backs
    if jersey <= 20:
        return Position.FORWARD
    return Position.BACK


class ESPNScraper(BaseScraper):
    """
    Scraper for ESPN Six Nations rugby API.

    Fetches:
    - Fixtures and results from scoreboard
    - Player rosters from match summaries
    - Detailed player statistics for completed matches
    """

    def __init__(
        self,
        base_url: str = ESPN_API_BASE,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 1,
    ) -> None:
        """
        Initialize the ESPN scraper.

        Args:
            base_url: ESPN API base URL.
            cache_dir: Directory for caching responses.
            cache_ttl_hours: Cache time-to-live in hours.
        """
        super().__init__(
            cache_dir=cache_dir,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_seconds=0.5,  # ESPN API is generous
        )
        self.base_url = base_url

    def scrape_fixtures(self, year: int = 2026, use_cache: bool = True) -> list[Match]:
        """
        Scrape all Six Nations fixtures for a given year.

        Args:
            year: Tournament year.
            use_cache: Whether to use cached data.

        Returns:
            List of Match objects.
        """
        url = f"{self.base_url}/scoreboard?dates={year}"
        data = self.fetch_json(url, use_cache=use_cache)

        matches = []
        events = data.get("events", [])

        # Parse all matches first
        parsed_matches = []
        for event in events:
            try:
                match_id = event.get("id", "")
                match_date = parse_espn_date(event.get("date", ""))

                # Extract teams
                competitions = event.get("competitions", [{}])
                if not competitions:
                    continue
                competition = competitions[0]

                competitors = competition.get("competitors", [])
                if len(competitors) != 2:
                    continue

                home_team = None
                away_team = None
                home_score = None
                away_score = None

                for comp in competitors:
                    team_name = comp.get("team", {}).get("displayName", "")
                    is_home = comp.get("homeAway") == "home"
                    score = comp.get("score")

                    if is_home:
                        home_team = team_name
                        home_score = int(score) if score else None
                    else:
                        away_team = team_name
                        away_score = int(score) if score else None

                if not home_team or not away_team:
                    continue

                parsed_matches.append({
                    "id": match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "home_score": home_score,
                    "away_score": away_score,
                })

            except (KeyError, ValueError, TypeError):
                continue

        # Sort by date and assign gameweeks (3 matches per gameweek)
        parsed_matches.sort(key=lambda m: m["match_date"])

        for i, match_data in enumerate(parsed_matches):
            # Six Nations has 3 matches per gameweek
            gameweek = min((i // 3) + 1, 5)

            matches.append(
                Match(
                    id=match_data["id"],
                    home_team=match_data["home_team"],
                    away_team=match_data["away_team"],
                    match_date=match_data["match_date"],
                    gameweek=gameweek,
                    home_score=match_data["home_score"],
                    away_score=match_data["away_score"],
                )
            )

        return matches

    def scrape_match_roster(
        self, match_id: str, use_cache: bool = True
    ) -> list[Player]:
        """
        Scrape player roster from a match summary.

        Args:
            match_id: ESPN match/event ID.
            use_cache: Whether to use cached data.

        Returns:
            List of Player objects (without prices).
        """
        url = f"{self.base_url}/summary?event={match_id}"
        data = self.fetch_json(url, use_cache=use_cache)

        players = []
        rosters = data.get("rosters", [])

        for team_roster in rosters:
            team_data = team_roster.get("team", {})
            team_id = int(team_data.get("id", 0))
            country = ESPN_TEAM_MAP.get(team_id)

            if not country:
                continue

            roster = team_roster.get("roster", [])
            for player_data in roster:
                try:
                    athlete = player_data.get("athlete", {})
                    player_id = athlete.get("id", "")
                    name = athlete.get("displayName", "")

                    # Get jersey number for position
                    jersey = int(player_data.get("jersey", 16))
                    position = jersey_to_position(jersey)

                    # Generate slug ID
                    slug_id = f"espn-{player_id}"

                    players.append(
                        Player(
                            id=slug_id,
                            name=name,
                            country=country,
                            position=position,
                            star_value=10.0,  # Default, will be updated from fantasy site
                        )
                    )

                except (KeyError, ValueError, TypeError):
                    continue

        return players

    def scrape_match_stats(
        self, match_id: str, use_cache: bool = True
    ) -> list[PlayerMatchStats]:
        """
        Scrape detailed player statistics from a completed match.

        Args:
            match_id: ESPN match/event ID.
            use_cache: Whether to use cached data.

        Returns:
            List of PlayerMatchStats objects.
        """
        url = f"{self.base_url}/summary?event={match_id}"
        data = self.fetch_json(url, use_cache=use_cache)

        stats_list = []
        boxscore = data.get("boxscore", {})
        players_data = boxscore.get("players", [])

        for team_data in players_data:
            team_stats = team_data.get("statistics", [])

            for stat_block in team_stats:
                athletes = stat_block.get("athletes", [])

                for athlete_data in athletes:
                    try:
                        athlete = athlete_data.get("athlete", {})
                        player_id = f"espn-{athlete.get('id', '')}"

                        # Determine if starter or sub
                        starter = athlete_data.get("starter", False)
                        selection_status = (
                            SelectionStatus.STARTER
                            if starter
                            else SelectionStatus.SUBSTITUTE
                        )

                        # Parse individual stats
                        raw_stats = athlete_data.get("stats", {})

                        # ESPN may provide player of match as "playerOfMatch" or similar
                        # Defaults to False if not provided
                        player_of_match = bool(raw_stats.get("playerOfMatch", False))

                        player_stats = PlayerMatchStats(
                            player_id=player_id,
                            match_id=match_id,
                            selection_status=selection_status,
                            tries=self._safe_int(raw_stats.get("tries", 0)),
                            try_assists=self._safe_int(raw_stats.get("tryAssists", 0)),
                            conversions=self._safe_int(raw_stats.get("conversionGoals", 0)),
                            penalty_kicks=self._safe_int(raw_stats.get("penaltyGoals", 0)),
                            drop_goals=self._safe_int(raw_stats.get("dropGoalsConverted", 0)),
                            metres_carried=self._safe_int(raw_stats.get("metresRun", 0)),
                            defenders_beaten=self._safe_int(raw_stats.get("defendersBeaten", 0)),
                            offloads=self._safe_int(raw_stats.get("offloads", 0)),
                            tackles=self._safe_int(raw_stats.get("tackles", 0)),
                            breakdown_steals=self._safe_int(raw_stats.get("turnoversWon", 0)),
                            lineout_steals=self._safe_int(raw_stats.get("lineoutWonSteals", 0)),
                            penalties_conceded=self._safe_int(raw_stats.get("penaltiesConceded", 0)),
                            yellow_cards=self._safe_int(raw_stats.get("yellowCards", 0)),
                            red_cards=self._safe_int(raw_stats.get("redCards", 0)),
                            player_of_match=player_of_match,
                        )

                        stats_list.append(player_stats)

                    except (KeyError, ValueError, TypeError):
                        continue

        return stats_list

    def _safe_int(self, value) -> int:
        """Safely convert value to int, defaulting to 0."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def scrape_all_players(
        self, year: int = 2026, use_cache: bool = True
    ) -> list[Player]:
        """
        Scrape all players from all scheduled matches.

        Args:
            year: Tournament year.
            use_cache: Whether to use cached data.

        Returns:
            List of unique Player objects.
        """
        fixtures = self.scrape_fixtures(year=year, use_cache=use_cache)

        # Use dict to deduplicate by player ID
        players_dict: dict[str, Player] = {}

        for match in fixtures:
            roster = self.scrape_match_roster(match.id, use_cache=use_cache)
            for player in roster:
                if player.id not in players_dict:
                    players_dict[player.id] = player

        return list(players_dict.values())

    def scrape(self, year: int = 2026, use_cache: bool = True) -> dict:
        """
        Scrape all Six Nations data.

        Args:
            year: Tournament year.
            use_cache: Whether to use cached data.

        Returns:
            Dictionary with 'fixtures', 'players', and 'stats' keys.
        """
        fixtures = self.scrape_fixtures(year=year, use_cache=use_cache)
        players = self.scrape_all_players(year=year, use_cache=use_cache)

        # Get stats for completed matches
        stats: dict[str, list[PlayerMatchStats]] = {}
        for match in fixtures:
            if match.is_completed:
                stats[match.id] = self.scrape_match_stats(
                    match.id, use_cache=use_cache
                )

        return {
            "fixtures": fixtures,
            "players": players,
            "stats": stats,
        }

    def scrape_roster_stats(
        self, match_id: str, use_cache: bool = True
    ) -> list[tuple[str, Country, Position, PlayerMatchStats]]:
        """
        Scrape detailed player statistics from roster data in a completed match.

        Uses rosters[].roster[].stats[] which contains a list of {name, value} dicts,
        rather than boxscore data.

        Args:
            match_id: ESPN match/event ID.
            use_cache: Whether to use cached data.

        Returns:
            List of (player_name, country, position, PlayerMatchStats) tuples.
        """
        url = f"{self.base_url}/summary?event={match_id}"
        data = self.fetch_json(url, use_cache=use_cache)

        results: list[tuple[str, Country, Position, PlayerMatchStats]] = []
        rosters = data.get("rosters", [])

        for team_roster in rosters:
            team_data = team_roster.get("team", {})
            team_id = int(team_data.get("id", 0))
            country = ESPN_TEAM_MAP.get(team_id)

            if not country:
                continue

            roster = team_roster.get("roster", [])
            for player_data in roster:
                try:
                    athlete = player_data.get("athlete", {})
                    player_name = athlete.get("displayName", "")

                    if not player_name:
                        continue

                    # Get jersey number for position
                    jersey_str = player_data.get("jersey", "16")
                    jersey = int(jersey_str) if jersey_str else 16
                    position = jersey_to_position(jersey)

                    # Determine if starter
                    starter = player_data.get("starter", False)
                    selection_status = (
                        SelectionStatus.STARTER if starter else SelectionStatus.SUBSTITUTE
                    )

                    # Parse stats from list format
                    stats_list = player_data.get("stats", [])
                    stats_dict: dict[str, float] = {}
                    for stat in stats_list:
                        if isinstance(stat, dict):
                            stat_name = stat.get("name", "")
                            stat_value = stat.get("value", 0)
                            if stat_name:
                                stats_dict[stat_name] = float(stat_value) if stat_value else 0.0

                    # Map ESPN stats to PlayerMatchStats fields
                    player_stats = PlayerMatchStats(
                        player_id=f"espn-{athlete.get('id', '')}",
                        match_id=match_id,
                        selection_status=selection_status,
                        tries=int(stats_dict.get("tries", 0)),
                        try_assists=int(stats_dict.get("tryAssists", 0)),
                        conversions=int(stats_dict.get("conversionGoals", 0)),
                        penalty_kicks=int(stats_dict.get("penaltyGoals", 0)),
                        drop_goals=int(stats_dict.get("dropGoalsConverted", 0)),
                        metres_carried=int(stats_dict.get("metres", 0)),
                        defenders_beaten=int(stats_dict.get("defendersBeaten", 0)),
                        offloads=int(stats_dict.get("offload", 0)),
                        tackles=int(stats_dict.get("tackles", 0)),
                        breakdown_steals=int(stats_dict.get("rucksWon", 0)),
                        lineout_steals=int(stats_dict.get("lineoutsWon", 0)),
                        penalties_conceded=int(stats_dict.get("penaltiesConceded", 0)),
                        yellow_cards=int(stats_dict.get("yellowCards", 0)),
                        red_cards=int(stats_dict.get("redCards", 0)),
                        player_of_match=False,  # Not available in roster stats
                    )

                    results.append((player_name, country, position, player_stats))

                except (KeyError, ValueError, TypeError):
                    continue

        return results

    def scrape_form_data(
        self, year: int = 2025, use_cache: bool = True
    ) -> list[tuple[str, Country, Position, PlayerMatchStats]]:
        """
        Collect per-player-per-match stats across all completed matches in a year.

        Args:
            year: Tournament year to scrape (default 2025 for form data).
            use_cache: Whether to use cached data.

        Returns:
            List of (player_name, country, position, PlayerMatchStats) tuples,
            one entry per player per match they played in.
        """
        fixtures = self.scrape_fixtures(year=year, use_cache=use_cache)
        all_stats: list[tuple[str, Country, Position, PlayerMatchStats]] = []

        for match in fixtures:
            if not match.is_completed:
                continue

            match_stats = self.scrape_roster_stats(match.id, use_cache=use_cache)
            all_stats.extend(match_stats)

        return all_stats

    def fetch_world_rankings(self, use_cache: bool = True) -> dict[Country, float]:
        """
        Fetch current World Rugby rankings for Six Nations teams.

        Args:
            use_cache: Whether to use cached data.

        Returns:
            Dict mapping Country to rating points (e.g., Ireland ~95, Italy ~75).
        """
        data = self.fetch_json(WORLD_RUGBY_RANKINGS_URL, use_cache=use_cache)

        rankings: dict[Country, float] = {}
        entries = data.get("entries", [])

        for entry in entries:
            team = entry.get("team", {})
            team_name = team.get("name", "")
            rating = float(entry.get("pts", 0.0))

            country = WORLD_RUGBY_TEAM_MAP.get(team_name)
            if country:
                rankings[country] = rating

        return rankings

    def scrape_starting_lineups(
        self, year: int = 2026, use_cache: bool = True
    ) -> dict[str, bool]:
        """
        Fetch starting lineup status for all players in upcoming/current matches.

        Args:
            year: Tournament year.
            use_cache: Whether to use cached data.

        Returns:
            Dict mapping player name (normalized) to is_starter status.
            Players not in any squad return False implicitly.
        """
        fixtures = self.scrape_fixtures(year=year, use_cache=use_cache)
        lineup_status: dict[str, bool] = {}

        for match in fixtures:
            url = f"{self.base_url}/summary?event={match.id}"
            data = self.fetch_json(url, use_cache=use_cache)

            rosters = data.get("rosters", [])
            for team_roster in rosters:
                roster = team_roster.get("roster", [])

                # Empty roster means lineups not yet announced
                if not roster:
                    continue

                for player_data in roster:
                    athlete = player_data.get("athlete", {})
                    player_name = athlete.get("displayName", "")

                    if not player_name:
                        continue

                    # Jersey 1-15 = starters, 16-23 = bench
                    # Also check starter field
                    starter = player_data.get("starter", False)
                    jersey_str = player_data.get("jersey", "")
                    jersey = int(jersey_str) if jersey_str else 99

                    is_starter = starter or (1 <= jersey <= 15)

                    # Use latest match info (don't overwrite starter with bench)
                    if player_name not in lineup_status or is_starter:
                        lineup_status[player_name] = is_starter

        return lineup_status
