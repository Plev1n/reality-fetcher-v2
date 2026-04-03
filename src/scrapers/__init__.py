"""Scraper registry with auto-discovery."""

from src.scrapers.base import BaseScraper

# Populated by @register decorator as scraper modules are imported
SCRAPERS: dict[str, type[BaseScraper]] = {}


def register(name: str):
    """Decorator to register a scraper class under a portal name."""
    def wrapper(cls):
        SCRAPERS[name] = cls
        return cls
    return wrapper


def import_all_scrapers() -> None:
    """Import all scraper modules to trigger @register decorators."""
    from src.scrapers import (  # noqa: F401
        sreality,
        idnes,
        realitymix,
        bezrealitky,
        bazos,
        realingo,
        eurobydleni,
        sousede,
        remaxcz,
        realitycz,
        realcity,
        realhit,
        century21,
        moravskereality,
        rksting,
        boreality,
        realityregio,
        mmreality,
    )
