"""Base scraper with caching and rate limiting."""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup


# Default cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


@dataclass
class CacheEntry:
    """Represents a cached response."""

    data: Any
    timestamp: datetime
    url: str


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class RateLimitError(ScraperError):
    """Raised when rate limit is exceeded."""

    pass


class FetchError(ScraperError):
    """Raised when fetching data fails."""

    pass


class ParseError(ScraperError):
    """Raised when parsing data fails."""

    pass


class BaseScraper(ABC):
    """
    Base scraper with caching and rate limiting.

    Subclasses should implement the abstract methods to define
    how to fetch and parse data from specific sources.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 1,
        rate_limit_seconds: float = 1.0,
    ) -> None:
        """
        Initialize the scraper.

        Args:
            cache_dir: Directory for caching responses.
            cache_ttl_hours: Cache time-to-live in hours.
            rate_limit_seconds: Minimum seconds between requests.
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time: Optional[float] = None

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Session for connection reuse
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "MoneyMaul/1.0 (Six Nations Fantasy Assistant)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def _cache_key(self, url: str) -> str:
        """Generate a cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _cache_path(self, url: str) -> Path:
        """Get the cache file path for a URL."""
        return self.cache_dir / f"{self._cache_key(url)}.json"

    def _read_cache(self, url: str) -> Optional[Any]:
        """
        Read cached data if valid.

        Args:
            url: The URL to look up in cache.

        Returns:
            Cached data if valid, None otherwise.
        """
        cache_path = self._cache_path(url)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                entry = json.load(f)

            timestamp = datetime.fromisoformat(entry["timestamp"])
            if datetime.now() - timestamp < self.cache_ttl:
                return entry["data"]
        except (json.JSONDecodeError, KeyError, ValueError):
            # Invalid cache entry, delete it
            cache_path.unlink(missing_ok=True)

        return None

    def _write_cache(self, url: str, data: Any) -> None:
        """
        Write data to cache.

        Args:
            url: The URL being cached.
            data: The data to cache.
        """
        cache_path = self._cache_path(url)
        entry = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        with open(cache_path, "w") as f:
            json.dump(entry, f)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str, use_cache: bool = True) -> str:
        """
        Fetch content from URL with caching and rate limiting.

        Args:
            url: The URL to fetch.
            use_cache: Whether to use cached data if available.

        Returns:
            The response text content.

        Raises:
            FetchError: If the request fails.
        """
        # Check cache first
        if use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                return cached

        # Apply rate limiting
        self._rate_limit()

        try:
            response = self._session.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise FetchError(f"Request timed out: {url}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise RateLimitError(f"Rate limited: {url}")
            raise FetchError(f"HTTP error {e.response.status_code}: {url}")
        except requests.exceptions.RequestException as e:
            raise FetchError(f"Request failed: {url} - {e}")

        content = response.text

        # Cache the response
        if use_cache:
            self._write_cache(url, content)

        return content

    def parse_html(self, content: str) -> BeautifulSoup:
        """
        Parse HTML content.

        Args:
            content: HTML string to parse.

        Returns:
            BeautifulSoup object.
        """
        return BeautifulSoup(content, "html.parser")

    def clear_cache(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of cache entries cleared.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            # Validate it's a cache entry before deletion
            try:
                with open(cache_file, "r") as f:
                    entry = json.load(f)
                if not all(k in entry for k in ("url", "timestamp", "data")):
                    continue
            except (json.JSONDecodeError, IOError):
                continue
            cache_file.unlink()
            count += 1
        return count

    def clear_expired_cache(self) -> int:
        """
        Clear expired cache entries.

        Returns:
            Number of cache entries cleared.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    entry = json.load(f)
                timestamp = datetime.fromisoformat(entry["timestamp"])
                if datetime.now() - timestamp >= self.cache_ttl:
                    cache_file.unlink()
                    count += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                cache_file.unlink()
                count += 1
        return count

    @abstractmethod
    def scrape(self) -> Any:
        """
        Scrape data from the source.

        Subclasses must implement this method.

        Returns:
            Scraped data in the appropriate format.
        """
        pass
