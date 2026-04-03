"""Base scraper with shared HTTP client and rate limiting."""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod

import httpx

from src.models import RawListing


class BaseScraper(ABC):
    """Abstract base for all portal scrapers."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    ]

    def __init__(
        self,
        timeout: float = 30.0,
        delay_range: tuple[float, float] = (1.0, 2.5),
    ):
        self._timeout = timeout
        self._delay_range = delay_range

    def _get_client(self) -> httpx.AsyncClient:
        """Create a new httpx client with random User-Agent."""
        return httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": random.choice(self.USER_AGENTS)},
            follow_redirects=True,
        )

    async def _delay(self) -> None:
        """Rate-limit delay between page requests."""
        await asyncio.sleep(random.uniform(*self._delay_range))

    @abstractmethod
    async def scrape(self, listing_type: str) -> list[RawListing]:
        """Scrape portal for given type (dum/pozemek/byt).

        Returns list of raw listings found.
        """
        ...
