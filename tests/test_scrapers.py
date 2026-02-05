"""Tests for scraper module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import Country, Player, PlayerMatchStats, Position, SelectionStatus
from src.scrapers import (
    BaseScraper,
    ESPNScraper,
    ESPN_AUTUMN_API_BASE,
    FetchError,
    ParseError,
    RateLimitError,
    FantasyScraper,
    StatsScraper,
    create_sample_match,
    create_sample_players,
    create_sample_stats,
    jersey_to_position,
    parse_country,
    parse_position,
)
from src.scrapers.prices import _calculate_scoring_only_points, calculate_form_based_points


class TestParseCountry:
    """Tests for parse_country function."""

    def test_full_names(self) -> None:
        """Test parsing full country names."""
        assert parse_country("England") == Country.ENGLAND
        assert parse_country("France") == Country.FRANCE
        assert parse_country("Ireland") == Country.IRELAND
        assert parse_country("Italy") == Country.ITALY
        assert parse_country("Scotland") == Country.SCOTLAND
        assert parse_country("Wales") == Country.WALES

    def test_lowercase(self) -> None:
        """Test parsing lowercase names."""
        assert parse_country("england") == Country.ENGLAND
        assert parse_country("france") == Country.FRANCE

    def test_abbreviations(self) -> None:
        """Test parsing country abbreviations."""
        assert parse_country("ENG") == Country.ENGLAND
        assert parse_country("FRA") == Country.FRANCE
        assert parse_country("IRE") == Country.IRELAND
        assert parse_country("ITA") == Country.ITALY
        assert parse_country("SCO") == Country.SCOTLAND
        assert parse_country("WAL") == Country.WALES

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is handled."""
        assert parse_country("  England  ") == Country.ENGLAND

    def test_unknown_country_raises_error(self) -> None:
        """Test that unknown country raises ParseError."""
        with pytest.raises(ParseError, match="Unknown country"):
            parse_country("Germany")


class TestParsePosition:
    """Tests for parse_position function."""

    def test_forward_positions(self) -> None:
        """Test parsing forward positions."""
        assert parse_position("Loosehead Prop") == Position.FORWARD
        assert parse_position("Hooker") == Position.FORWARD
        assert parse_position("Lock") == Position.FORWARD
        assert parse_position("Flanker") == Position.FORWARD
        assert parse_position("Number 8") == Position.FORWARD

    def test_back_positions(self) -> None:
        """Test parsing back positions."""
        assert parse_position("Scrum-half") == Position.BACK
        assert parse_position("Fly-half") == Position.BACK
        assert parse_position("Centre") == Position.BACK
        assert parse_position("Wing") == Position.BACK
        assert parse_position("Full-back") == Position.BACK

    def test_alternative_spellings(self) -> None:
        """Test alternative position spellings."""
        assert parse_position("Fullback") == Position.BACK
        assert parse_position("Full Back") == Position.BACK
        assert parse_position("Scrum Half") == Position.BACK
        assert parse_position("No. 8") == Position.FORWARD

    def test_inferred_positions(self) -> None:
        """Test positions inferred from common patterns."""
        assert parse_position("Tighthead Prop") == Position.FORWARD
        assert parse_position("Inside Centre") == Position.BACK

    def test_unknown_position_raises_error(self) -> None:
        """Test that unknown position raises ParseError."""
        with pytest.raises(ParseError, match="Unknown position"):
            parse_position("Goalkeeper")


class TestBaseScraper:
    """Tests for BaseScraper caching functionality."""

    def test_cache_key_generation(self) -> None:
        """Test that cache keys are generated consistently."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class DummyScraper(BaseScraper):
                def scrape(self):
                    return None

            scraper = DummyScraper(cache_dir=Path(tmpdir))
            key1 = scraper._cache_key("https://example.com/test")
            key2 = scraper._cache_key("https://example.com/test")
            key3 = scraper._cache_key("https://example.com/other")

            assert key1 == key2
            assert key1 != key3

    def test_cache_write_and_read(self) -> None:
        """Test writing and reading from cache."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class DummyScraper(BaseScraper):
                def scrape(self):
                    return None

            scraper = DummyScraper(cache_dir=Path(tmpdir))
            url = "https://example.com/test"
            data = "<html>test content</html>"

            scraper._write_cache(url, data)
            cached = scraper._read_cache(url)

            assert cached == data

    def test_cache_expiry(self) -> None:
        """Test that expired cache entries are not returned."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class DummyScraper(BaseScraper):
                def scrape(self):
                    return None

            scraper = DummyScraper(cache_dir=Path(tmpdir), cache_ttl_hours=1)
            url = "https://example.com/test"
            data = "<html>test content</html>"

            # Write cache entry manually with old timestamp
            cache_path = scraper._cache_path(url)
            old_timestamp = datetime.now() - timedelta(hours=2)
            entry = {
                "url": url,
                "timestamp": old_timestamp.isoformat(),
                "data": data,
            }
            with open(cache_path, "w") as f:
                json.dump(entry, f)

            # Should return None for expired entry
            cached = scraper._read_cache(url)
            assert cached is None

    def test_clear_cache(self) -> None:
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class DummyScraper(BaseScraper):
                def scrape(self):
                    return None

            scraper = DummyScraper(cache_dir=Path(tmpdir))

            # Write some cache entries
            scraper._write_cache("https://example.com/1", "data1")
            scraper._write_cache("https://example.com/2", "data2")

            count = scraper.clear_cache()
            assert count == 2
            assert scraper._read_cache("https://example.com/1") is None
            assert scraper._read_cache("https://example.com/2") is None

    def test_clear_expired_cache(self) -> None:
        """Test clearing only expired cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class DummyScraper(BaseScraper):
                def scrape(self):
                    return None

            scraper = DummyScraper(cache_dir=Path(tmpdir), cache_ttl_hours=1)

            # Write a fresh entry
            scraper._write_cache("https://example.com/fresh", "fresh data")

            # Write an expired entry manually
            old_timestamp = datetime.now() - timedelta(hours=2)
            cache_path = scraper._cache_path("https://example.com/old")
            entry = {
                "url": "https://example.com/old",
                "timestamp": old_timestamp.isoformat(),
                "data": "old data",
            }
            with open(cache_path, "w") as f:
                json.dump(entry, f)

            count = scraper.clear_expired_cache()
            assert count == 1
            assert scraper._read_cache("https://example.com/fresh") == "fresh data"


class TestSampleData:
    """Tests for sample data creation functions."""

    def test_create_sample_players(self) -> None:
        """Test sample player creation."""
        players = create_sample_players()

        assert len(players) >= 6  # At least one per country
        assert all(player.star_value > 0 for player in players)
        assert all(player.ownership_pct is not None for player in players)

        # Check country diversity
        countries = {player.country for player in players}
        assert Country.ENGLAND in countries
        assert Country.FRANCE in countries

    def test_create_sample_match(self) -> None:
        """Test sample match creation."""
        match = create_sample_match()

        assert match.id
        assert match.home_team
        assert match.away_team
        assert match.gameweek >= 1
        assert match.gameweek <= 5

    def test_create_sample_stats(self) -> None:
        """Test sample player stats creation."""
        stats = create_sample_stats()

        assert len(stats) >= 1
        assert all(stat.match_id for stat in stats)
        assert all(stat.player_id for stat in stats)

        # Check that at least one player has some stats
        has_stats = any(
            stat.tries > 0
            or stat.tackles > 0
            or stat.metres_carried > 0
            for stat in stats
        )
        assert has_stats

    def test_sample_stats_includes_substitute(self) -> None:
        """Test that sample stats include a substitute player."""
        stats = create_sample_stats()

        has_sub = any(
            stat.selection_status == SelectionStatus.SUBSTITUTE for stat in stats
        )
        assert has_sub

    def test_sample_stats_includes_player_of_match(self) -> None:
        """Test that sample stats include a player of the match."""
        stats = create_sample_stats()

        has_potm = any(stat.player_of_match for stat in stats)
        assert has_potm


class TestFantasyScraper:
    """Tests for FantasyScraper."""

    def test_initialization(self) -> None:
        """Test scraper initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = FantasyScraper(cache_dir=Path(tmpdir))

            assert scraper.base_url
            assert scraper.cache_dir == Path(tmpdir)

    @patch("src.scrapers.base.BaseScraper.fetch")
    def test_scrape_returns_empty_for_invalid_html(
        self, mock_fetch: MagicMock
    ) -> None:
        """Test that scraping returns empty list for invalid HTML."""
        mock_fetch.return_value = "<html><body>No players here</body></html>"

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = FantasyScraper(cache_dir=Path(tmpdir))
            players = scraper.scrape()

            assert players == []


class TestStatsScraper:
    """Tests for StatsScraper."""

    def test_initialization(self) -> None:
        """Test scraper initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = StatsScraper(cache_dir=Path(tmpdir))

            assert scraper.base_url
            assert scraper.cache_dir == Path(tmpdir)

    @patch("src.scrapers.base.BaseScraper.fetch")
    def test_scrape_fixtures_returns_empty_for_invalid_html(
        self, mock_fetch: MagicMock
    ) -> None:
        """Test that scraping returns empty list for invalid HTML."""
        mock_fetch.return_value = "<html><body>No fixtures here</body></html>"

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = StatsScraper(cache_dir=Path(tmpdir))
            matches = scraper.scrape_fixtures()

            assert matches == []


class TestJerseyToPosition:
    """Tests for jersey_to_position function."""

    def test_forward_jerseys(self) -> None:
        """Test that jerseys 1-8 return FORWARD."""
        for jersey in range(1, 9):
            assert jersey_to_position(jersey) == Position.FORWARD

    def test_back_jerseys(self) -> None:
        """Test that jerseys 9-15 return BACK."""
        for jersey in range(9, 16):
            assert jersey_to_position(jersey) == Position.BACK

    def test_bench_forwards(self) -> None:
        """Test that bench jerseys 16-20 return FORWARD."""
        for jersey in range(16, 21):
            assert jersey_to_position(jersey) == Position.FORWARD

    def test_bench_backs(self) -> None:
        """Test that bench jerseys 21-23 return BACK."""
        for jersey in range(21, 24):
            assert jersey_to_position(jersey) == Position.BACK

    def test_invalid_jersey_zero_raises_error(self) -> None:
        """Test that jersey 0 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid jersey number"):
            jersey_to_position(0)

    def test_invalid_jersey_negative_raises_error(self) -> None:
        """Test that negative jersey raises ValueError."""
        with pytest.raises(ValueError, match="Invalid jersey number"):
            jersey_to_position(-1)

    def test_invalid_jersey_too_high_raises_error(self) -> None:
        """Test that jersey > 23 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid jersey number"):
            jersey_to_position(24)


class TestESPNScraper:
    """Tests for ESPNScraper."""

    def test_initialization(self) -> None:
        """Test scraper initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))

            assert scraper.base_url
            assert scraper.cache_dir == Path(tmpdir)

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_fixtures_parses_events(self, mock_fetch_json: MagicMock) -> None:
        """Test that fixtures are parsed from ESPN scoreboard response."""
        mock_fetch_json.return_value = {
            "events": [
                {
                    "id": "602502",
                    "date": "2026-02-01T15:15Z",
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {"displayName": "France"},
                                    "homeAway": "home",
                                    "score": "32",
                                },
                                {
                                    "team": {"displayName": "Ireland"},
                                    "homeAway": "away",
                                    "score": "19",
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_fixtures()

            assert len(fixtures) == 1
            assert fixtures[0].id == "602502"
            assert fixtures[0].home_team == "France"
            assert fixtures[0].away_team == "Ireland"
            assert fixtures[0].home_score == 32
            assert fixtures[0].away_score == 19

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_fixtures_handles_scheduled_match(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that scheduled matches (no score) are handled."""
        mock_fetch_json.return_value = {
            "events": [
                {
                    "id": "602516",
                    "date": "2026-03-15T17:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {"displayName": "France"},
                                    "homeAway": "home",
                                    "score": None,
                                },
                                {
                                    "team": {"displayName": "England"},
                                    "homeAway": "away",
                                    "score": None,
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_fixtures()

            assert len(fixtures) == 1
            assert fixtures[0].home_score is None
            assert fixtures[0].away_score is None
            assert not fixtures[0].is_completed

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_match_roster_parses_players(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that player rosters are parsed from match summary."""
        mock_fetch_json.return_value = {
            "rosters": [
                {
                    "team": {"id": "9"},  # France
                    "roster": [
                        {
                            "athlete": {
                                "id": "12345",
                                "displayName": "Antoine Dupont",
                            },
                            "jersey": "9",
                        },
                        {
                            "athlete": {
                                "id": "12346",
                                "displayName": "Gregory Alldritt",
                            },
                            "jersey": "8",
                        },
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            roster = scraper.scrape_match_roster("602502")

            assert len(roster) == 2
            # Dupont is a scrum-half (9) - BACK
            dupont = next(p for p in roster if "Dupont" in p.name)
            assert dupont.country == Country.FRANCE
            assert dupont.position == Position.BACK
            # Alldritt is a No.8 - FORWARD
            alldritt = next(p for p in roster if "Alldritt" in p.name)
            assert alldritt.position == Position.FORWARD

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_match_stats_parses_statistics(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that player statistics are parsed from match summary."""
        mock_fetch_json.return_value = {
            "boxscore": {
                "players": [
                    {
                        "statistics": [
                            {
                                "athletes": [
                                    {
                                        "athlete": {"id": "12345"},
                                        "starter": True,
                                        "stats": {
                                            "tries": 2,
                                            "tryAssists": 1,
                                            "metresRun": 75,
                                            "tackles": 8,
                                            "turnoversWon": 1,
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            stats = scraper.scrape_match_stats("602502")

            assert len(stats) == 1
            assert stats[0].player_id == "espn-12345"
            assert stats[0].match_id == "602502"
            assert stats[0].selection_status == SelectionStatus.STARTER
            assert stats[0].tries == 2
            assert stats[0].try_assists == 1
            assert stats[0].metres_carried == 75
            assert stats[0].tackles == 8
            assert stats[0].breakdown_steals == 1

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_returns_empty_for_malformed_data(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that scraping handles malformed data gracefully."""
        mock_fetch_json.return_value = {"events": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_fixtures()

            assert fixtures == []

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_gameweek_assignment_by_match_order(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that gameweeks are assigned based on match order (3 per GW)."""
        # Create 6 mock events (2 gameweeks worth) with proper date format
        mock_fetch_json.return_value = {
            "events": [
                {
                    "id": str(i),
                    "date": f"2026-02-{5 + i:02d}T15:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"displayName": f"Team{i}A"}, "homeAway": "home", "score": None},
                                {"team": {"displayName": f"Team{i}B"}, "homeAway": "away", "score": None},
                            ]
                        }
                    ],
                }
                for i in range(6)
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_fixtures()

            assert len(fixtures) == 6
            # First 3 matches should be GW1
            assert fixtures[0].gameweek == 1
            assert fixtures[1].gameweek == 1
            assert fixtures[2].gameweek == 1
            # Next 3 should be GW2
            assert fixtures[3].gameweek == 2
            assert fixtures[4].gameweek == 2
            assert fixtures[5].gameweek == 2


class TestAutumnFixtures:
    """Tests for Autumn Internationals fixture scraping."""

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_autumn_fixtures_filters_six_nations(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that non-Six-Nations matches are excluded."""
        # Return two matches: one with France (id=9), one with Argentina (id=11) vs South Africa (id=13)
        mock_fetch_json.return_value = {
            "events": [
                {
                    "id": "401001",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"id": "9"}, "homeAway": "home", "score": "30"},
                                {"team": {"id": "5"}, "homeAway": "away", "score": "20"},
                            ]
                        }
                    ],
                },
                {
                    "id": "401002",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"id": "11"}, "homeAway": "home", "score": "25"},
                                {"team": {"id": "13"}, "homeAway": "away", "score": "18"},
                            ]
                        }
                    ],
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_autumn_fixtures()

            # Only the France match should be included
            assert len(fixtures) == 1
            assert fixtures[0]["id"] == "401001"
            assert fixtures[0]["home_team_id"] == 9
            assert fixtures[0]["completed"] is True

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_autumn_fixtures_handles_api_error(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test graceful handling when API call fails."""
        mock_fetch_json.side_effect = Exception("API error")

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            fixtures = scraper.scrape_autumn_fixtures()

            assert fixtures == []


class TestPlayByPlay:
    """Tests for play-by-play scraping."""

    def _make_summary_response(self) -> dict:
        """Create a mock match summary with play-by-play details."""
        return {
            "rosters": [
                {
                    "team": {"id": "9"},  # France
                    "roster": [
                        {
                            "athlete": {"id": "100", "displayName": "Thomas Ramos"},
                            "jersey": "15",
                            "starter": True,
                        },
                        {
                            "athlete": {"id": "101", "displayName": "Antoine Dupont"},
                            "jersey": "9",
                            "starter": True,
                        },
                        {
                            "athlete": {"id": "102", "displayName": "Gregory Alldritt"},
                            "jersey": "8",
                            "starter": True,
                        },
                        {
                            "athlete": {"id": "103", "displayName": "Peato Mauvaka"},
                            "jersey": "16",
                            "starter": False,
                        },
                    ],
                },
                {
                    "team": {"id": "5"},  # Non-Six-Nations team (e.g., New Zealand)
                    "roster": [
                        {
                            "athlete": {"id": "200", "displayName": "Damian McKenzie"},
                            "jersey": "10",
                            "starter": True,
                        },
                    ],
                },
            ],
            "details": [
                {
                    "type": {"text": "Try"},
                    "participants": [
                        {"athlete": {"displayName": "Antoine Dupont"}},
                    ],
                },
                {
                    "type": {"text": "Conversion"},
                    "participants": [
                        {"athlete": {"displayName": "Thomas Ramos"}},
                    ],
                },
                {
                    "type": {"text": "Penalty Goal"},
                    "participants": [
                        {"athlete": {"displayName": "Thomas Ramos"}},
                    ],
                },
                {
                    "type": {"text": "Try"},
                    "participants": [
                        {"athlete": {"displayName": "Antoine Dupont"}},
                    ],
                },
                {
                    "type": {"text": "Yellow Card"},
                    "participants": [
                        {"athlete": {"displayName": "Gregory Alldritt"}},
                    ],
                },
                {
                    "type": {"text": "Substitution"},
                    "participants": [
                        {"athlete": {"displayName": "Peato Mauvaka"}},
                    ],
                },
            ],
        }

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_play_by_play_parses_scoring_events(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test parsing scoring events into PlayerMatchStats."""
        mock_fetch_json.return_value = self._make_summary_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            results = scraper.scrape_play_by_play("401001")

            # Find Dupont's stats (2 tries)
            dupont = [r for r in results if r[0] == "Antoine Dupont"]
            assert len(dupont) == 1
            name, country, position, stats = dupont[0]
            assert country == Country.FRANCE
            assert position == Position.BACK
            assert stats.tries == 2

            # Find Ramos's stats (1 conversion, 1 penalty)
            ramos = [r for r in results if r[0] == "Thomas Ramos"]
            assert len(ramos) == 1
            _, _, _, ramos_stats = ramos[0]
            assert ramos_stats.conversions == 1
            assert ramos_stats.penalty_kicks == 1

            # Alldritt got a yellow card
            alldritt = [r for r in results if r[0] == "Gregory Alldritt"]
            assert len(alldritt) == 1
            _, _, _, alldritt_stats = alldritt[0]
            assert alldritt_stats.yellow_cards == 1

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_play_by_play_includes_non_scoring_players(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that players with no scoring events are still included."""
        mock_fetch_json.return_value = self._make_summary_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            results = scraper.scrape_play_by_play("401001")

            # Mauvaka is in roster but only has a substitution event (not mapped)
            mauvaka = [r for r in results if r[0] == "Peato Mauvaka"]
            assert len(mauvaka) == 1
            _, country, _, stats = mauvaka[0]
            assert country == Country.FRANCE
            assert stats.tries == 0
            assert stats.conversions == 0
            assert stats.selection_status == SelectionStatus.SUBSTITUTE

    @patch("src.scrapers.base.BaseScraper.fetch_json")
    def test_scrape_play_by_play_excludes_non_six_nations(
        self, mock_fetch_json: MagicMock
    ) -> None:
        """Test that non-Six-Nations team players are excluded from results."""
        mock_fetch_json.return_value = self._make_summary_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            scraper = ESPNScraper(cache_dir=Path(tmpdir))
            results = scraper.scrape_play_by_play("401001")

            # Only France players (team id 9) should be included
            # New Zealand (team id 5) is not in ESPN_TEAM_MAP
            player_names = [r[0] for r in results]
            assert "Damian McKenzie" not in player_names
            assert len(results) == 4  # 4 French players only


class TestScoringOnlyPoints:
    """Tests for _calculate_scoring_only_points helper."""

    def test_basic_scoring_events(self) -> None:
        """Test that scoring-only points are a subset of full points."""
        from src.analysis.calculator import calculate_base_points

        stats = PlayerMatchStats(
            player_id="test-1",
            match_id="m1",
            tries=1,
            conversions=2,
            penalty_kicks=1,
            metres_carried=50,
            tackles=8,
            defenders_beaten=3,
        )

        full = calculate_base_points(stats, Position.BACK)
        scoring_only = _calculate_scoring_only_points(stats, Position.BACK)

        # Scoring only should be less than full (missing metres, tackles, defenders beaten)
        assert scoring_only < full
        # But should include tries (10), conversions (4), penalty (3) = 17
        assert scoring_only == 10 + 4 + 3

    def test_forward_try_scoring(self) -> None:
        """Test forward try value in scoring-only calculation."""
        stats = PlayerMatchStats(
            player_id="test-2",
            match_id="m1",
            tries=1,
        )

        forward_pts = _calculate_scoring_only_points(stats, Position.FORWARD)
        back_pts = _calculate_scoring_only_points(stats, Position.BACK)

        assert forward_pts == 15  # Forward try
        assert back_pts == 10    # Back try

    def test_cards_reduce_scoring_points(self) -> None:
        """Test that yellow/red cards reduce scoring-only points."""
        stats = PlayerMatchStats(
            player_id="test-3",
            match_id="m1",
            tries=1,
            yellow_cards=1,
        )

        pts = _calculate_scoring_only_points(stats, Position.BACK)
        assert pts == 10 - 5  # Try (10) minus yellow card (-5)

    def test_zero_stats_returns_zero(self) -> None:
        """Test that a player with no scoring events gets 0."""
        stats = PlayerMatchStats(
            player_id="test-4",
            match_id="m1",
            metres_carried=100,
            tackles=15,
            offloads=3,
        )

        pts = _calculate_scoring_only_points(stats, Position.FORWARD)
        assert pts == 0.0


class TestCalibrationLogic:
    """Tests for Autumn calibration in calculate_form_based_points."""

    def _make_players(self) -> list[Player]:
        """Create test players."""
        return [
            Player(id="fra-dupont", name="A. Dupont", country=Country.FRANCE,
                   position=Position.BACK, star_value=16.0),
            Player(id="fra-ramos", name="T. Ramos", country=Country.FRANCE,
                   position=Position.BACK, star_value=14.0),
            Player(id="eng-smith", name="M. Smith", country=Country.ENGLAND,
                   position=Position.BACK, star_value=12.0),
        ]

    @patch("src.scrapers.prices.load_static_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_starting_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_autumn_form_data")
    @patch("src.scrapers.espn.ESPNScraper.scrape_form_data")
    def test_calibration_ratio_applied_correctly(
        self, mock_sn_form: MagicMock, mock_autumn_form: MagicMock,
        mock_lineups: MagicMock, mock_static_lineups: MagicMock,
    ) -> None:
        """Test that personal calibration ratio is applied to autumn data."""
        players = self._make_players()

        # Six Nations: Dupont scored 50 full, 20 scoring-only per match
        # → personal ratio = 50/20 = 2.5
        sn_stats = PlayerMatchStats(
            player_id="espn-101", match_id="sn1",
            selection_status=SelectionStatus.STARTER,
            tries=2, metres_carried=60, tackles=8, defenders_beaten=4, offloads=2,
        )
        mock_sn_form.return_value = [
            ("Antoine Dupont", Country.FRANCE, Position.BACK, sn_stats),
        ]

        # Autumn: Dupont scored 10 scoring-only per match (1 try)
        autumn_stats = PlayerMatchStats(
            player_id="espn-101", match_id="au1",
            selection_status=SelectionStatus.STARTER,
            tries=1,
        )
        mock_autumn_form.return_value = [
            ("Antoine Dupont", Country.FRANCE, Position.BACK, autumn_stats),
        ]

        mock_static_lineups.return_value = {"Antoine Dupont": True}
        mock_lineups.return_value = {}

        result = calculate_form_based_points(
            players, include_autumn=True, autumn_weight=0.6,
        )

        # Dupont should have blended points with 1.2x starter bonus
        assert "fra-dupont" in result
        # sn_full = 50 (approx - calculated from stats above)
        # personal_ratio = sn_full / sn_scoring
        # autumn_estimated = 10 * ratio
        # blended = 0.4 * sn_full + 0.6 * autumn_estimated
        # final = blended * 1.2 (starter)
        # Just verify it's in a reasonable range (not the star_value fallback)
        assert result["fra-dupont"] > 20.0

    @patch("src.scrapers.prices.load_static_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_starting_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_autumn_form_data")
    @patch("src.scrapers.espn.ESPNScraper.scrape_form_data")
    def test_autumn_only_player_uses_position_ratio(
        self, mock_sn_form: MagicMock, mock_autumn_form: MagicMock,
        mock_lineups: MagicMock, mock_static_lineups: MagicMock,
    ) -> None:
        """Test that a player with only Autumn data uses position-average ratio."""
        players = self._make_players()

        # Six Nations: Dupont provides calibration data
        sn_stats = PlayerMatchStats(
            player_id="espn-101", match_id="sn1",
            selection_status=SelectionStatus.STARTER,
            tries=2, metres_carried=60, tackles=8, defenders_beaten=4, offloads=2,
        )
        mock_sn_form.return_value = [
            ("Antoine Dupont", Country.FRANCE, Position.BACK, sn_stats),
        ]

        # Autumn: Smith only has autumn data (new cap / didn't play in 2025 Six Nations)
        autumn_stats = PlayerMatchStats(
            player_id="espn-301", match_id="au1",
            selection_status=SelectionStatus.STARTER,
            tries=1,
        )
        mock_autumn_form.return_value = [
            ("Marcus Smith", Country.ENGLAND, Position.BACK, autumn_stats),
        ]

        mock_static_lineups.return_value = {"Marcus Smith": True}
        mock_lineups.return_value = {}

        result = calculate_form_based_points(
            players, include_autumn=True, autumn_weight=0.6,
        )

        # Smith should have estimated points using position-average ratio
        assert "eng-smith" in result
        # Should be higher than star_value fallback (12 * 1.5 = 18)
        assert result["eng-smith"] > 18.0

    @patch("src.scrapers.prices.load_static_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_starting_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_autumn_form_data")
    @patch("src.scrapers.espn.ESPNScraper.scrape_form_data")
    def test_autumn_fallback_on_error(
        self, mock_sn_form: MagicMock, mock_autumn_form: MagicMock,
        mock_lineups: MagicMock, mock_static_lineups: MagicMock,
    ) -> None:
        """Test that API error in autumn scraping falls back gracefully."""
        players = self._make_players()

        sn_stats = PlayerMatchStats(
            player_id="espn-101", match_id="sn1",
            selection_status=SelectionStatus.STARTER,
            tries=2, metres_carried=60, tackles=8, defenders_beaten=4, offloads=2,
        )
        mock_sn_form.return_value = [
            ("Antoine Dupont", Country.FRANCE, Position.BACK, sn_stats),
        ]

        # Autumn scraping raises an exception
        mock_autumn_form.side_effect = Exception("Network error")

        mock_static_lineups.return_value = {"Antoine Dupont": True}
        mock_lineups.return_value = {}

        # Should not raise - falls back to Six Nations only
        result = calculate_form_based_points(
            players, include_autumn=True, autumn_weight=0.6,
        )

        assert "fra-dupont" in result
        # Points should still be calculated from Six Nations data
        assert result["fra-dupont"] > 20.0

    @patch("src.scrapers.prices.load_static_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_starting_lineups")
    @patch("src.scrapers.espn.ESPNScraper.scrape_form_data")
    def test_include_autumn_false_backward_compat(
        self, mock_sn_form: MagicMock,
        mock_lineups: MagicMock, mock_static_lineups: MagicMock,
    ) -> None:
        """Test that include_autumn=False gives same behavior as before."""
        players = self._make_players()

        sn_stats = PlayerMatchStats(
            player_id="espn-101", match_id="sn1",
            selection_status=SelectionStatus.STARTER,
            tries=2, metres_carried=60, tackles=8, defenders_beaten=4, offloads=2,
        )
        mock_sn_form.return_value = [
            ("Antoine Dupont", Country.FRANCE, Position.BACK, sn_stats),
        ]

        mock_static_lineups.return_value = {"Antoine Dupont": True}
        mock_lineups.return_value = {}

        # With include_autumn=False, should not attempt to scrape autumn data
        result = calculate_form_based_points(
            players, include_autumn=False,
        )

        assert "fra-dupont" in result
        # Unmatched players get fallback
        assert "eng-smith" in result
