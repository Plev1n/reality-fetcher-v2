"""Data models for reality-fetcher v2."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawListing:
    """Raw listing data from a portal, before normalization."""
    portal: str
    portal_id: str
    title: str
    url: str
    type_raw: str | None = None
    price_raw: str | None = None
    area_raw: str | None = None
    location_raw: str | None = None
    address_raw: str | None = None
    description: str | None = None
    coordinates: tuple[float, float] | None = None
    images: list[str] = field(default_factory=list)


@dataclass
class NormalizedListing:
    """Normalized listing ready for storage and display."""
    portal: str
    portal_id: str
    title: str
    url: str
    type: str                              # "dum" | "pozemek" | "byt"
    price: int | None
    price_unknown: bool
    area_m2: int | None
    area_unknown: bool
    price_per_m2: int | None
    location: str                          # Canonical locality name
    location_id: str                       # Locality ID for filtering
    coordinates: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for data file storage."""
        today = date.today().isoformat()
        return {
            "id": f"{self.portal}_{self.portal_id}",
            "status": "active",
            "type": self.type,
            "title": self.title,
            "location": self.location,
            "location_id": self.location_id,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "area_m2": self.area_m2,
            "price": self.price,
            "price_per_m2": self.price_per_m2,
            "price_unknown": self.price_unknown,
            "area_unknown": self.area_unknown,
            "url": self.url,
            "portal": self.portal,
            "added": today,
            "updated": today,
            "price_history": [{"date": today, "price": self.price}] if self.price else [],
            "removed_date": None,
        }
