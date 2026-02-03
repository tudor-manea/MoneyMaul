"""Tests for scraper module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import Country, Position, SelectionStatus
from src.scrapers import (
    BaseScraper,
    FetchError,
    ParseError,
    RateLimitError,
    FantasyScraper,
    StatsScraper,
    create_sample_match,
    create_sample_players,
    create_sample_stats,
    parse_country,
    parse_position,
)


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
