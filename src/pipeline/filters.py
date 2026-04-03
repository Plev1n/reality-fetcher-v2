"""Filter pipeline for rejecting irrelevant listings."""

import unicodedata
from dataclasses import dataclass
from abc import ABC, abstractmethod
from src.models import NormalizedListing


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""


class BaseFilter(ABC):
    @abstractmethod
    def check(self, listing: NormalizedListing) -> FilterResult: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class TypeFilter(BaseFilter):
    def __init__(self, allowed_types: list[str]) -> None:
        self._allowed = set(allowed_types)

    @property
    def name(self) -> str:
        return "TypeFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.type in self._allowed:
            return FilterResult(passed=True)
        return FilterResult(passed=False, reason=f"Type '{listing.type}' not in {self._allowed}")


class PriceFilter(BaseFilter):
    def __init__(self, max_price: int) -> None:
        self._max = max_price

    @property
    def name(self) -> str:
        return "PriceFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.price_unknown or listing.price is None:
            return FilterResult(passed=True)
        if listing.price > self._max:
            return FilterResult(passed=False, reason=f"Price {listing.price} > max {self._max}")
        return FilterResult(passed=True)


class AreaFilter(BaseFilter):
    def __init__(self, min_area: int) -> None:
        self._min = min_area

    @property
    def name(self) -> str:
        return "AreaFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.area_unknown or listing.area_m2 is None:
            return FilterResult(passed=True)
        if listing.area_m2 < self._min:
            return FilterResult(passed=False, reason=f"Area {listing.area_m2} < min {self._min}")
        return FilterResult(passed=True)


class LocationFilter(BaseFilter):
    def __init__(self, active_ids: set[str]) -> None:
        self._active = active_ids

    @property
    def name(self) -> str:
        return "LocationFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.location_id in self._active:
            return FilterResult(passed=True)
        return FilterResult(passed=False, reason=f"Location '{listing.location_id}' not in whitelist")


class BlacklistFilter(BaseFilter):
    def __init__(self, words: list[str]) -> None:
        self._words = words

    @property
    def name(self) -> str:
        return "BlacklistFilter"

    def _strip_diacritics(self, text: str) -> str:
        nfkd = unicodedata.normalize("NFD", text)
        return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

    def check(self, listing: NormalizedListing) -> FilterResult:
        text = f"{listing.title} {listing.url}".lower()
        text_ascii = self._strip_diacritics(text)
        for word in self._words:
            word_lower = word.lower()
            word_ascii = self._strip_diacritics(word_lower)
            if word_lower in text or word_ascii in text_ascii:
                return FilterResult(passed=False, reason=f"Blacklisted: '{word}'")
        return FilterResult(passed=True)


class URLPatternFilter(BaseFilter):
    def __init__(self, patterns: list[str]) -> None:
        self._patterns = [p.lower() for p in patterns]

    @property
    def name(self) -> str:
        return "URLPatternFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        url = listing.url.lower()
        for p in self._patterns:
            if p in url:
                return FilterResult(passed=False, reason=f"URL contains '{p}'")
        return FilterResult(passed=True)


class FilterPipeline:
    def __init__(self, filters: list[BaseFilter] | None = None) -> None:
        self._filters = filters or []

    def apply(self, listing: NormalizedListing) -> bool:
        for f in self._filters:
            if not f.check(listing).passed:
                return False
        return True

    @classmethod
    def create(
        cls,
        allowed_types: list[str],
        max_price: int,
        min_area: int,
        active_locality_ids: set[str],
        blacklist_words: list[str],
        url_blocked_patterns: list[str] | None = None,
    ) -> "FilterPipeline":
        filters: list[BaseFilter] = [TypeFilter(allowed_types)]
        if url_blocked_patterns:
            filters.append(URLPatternFilter(url_blocked_patterns))
        filters.extend([
            PriceFilter(max_price),
            AreaFilter(min_area),
            LocationFilter(active_locality_ids),
            BlacklistFilter(blacklist_words),
        ])
        return cls(filters)
