"""Score a listing against a similarity profile (0–100)."""

from __future__ import annotations

from src.similar.details import ListingDetails

WEIGHTS = {"price": 25, "usable_area": 25, "plot_area": 25, "rooms": 10, "location": 15}


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _range_fraction(value: int | None, spec: dict) -> float | None:
    """1.0 inside the ideal band, linear falloff to 0 at min/max, None if value unknown."""
    if value is None:
        return None
    lo, ilo, ihi, hi = spec["min"], spec["ideal_min"], spec["ideal_max"], spec["max"]
    if ilo <= value <= ihi:
        return 1.0
    if lo <= value < ilo:
        return (value - lo) / (ilo - lo) if ilo > lo else 1.0
    if ihi < value <= hi:
        return (hi - value) / (hi - ihi) if hi > ihi else 1.0
    return 0.0


def _mark(frac: float) -> str:
    return "✓" if frac >= 0.999 else ("~" if frac > 0 else "✗")


def score_listing(listing: dict, details: ListingDetails | None, profile: dict) -> tuple[int, list[str]]:
    """Return (score 0–100, Czech reasons). Unknown values earn half of their weight."""
    det = details if details is not None and details.ok else None
    total = 0.0
    reasons: list[str] = []

    price = listing.get("price")
    f = _range_fraction(price, profile["price"])
    if f is None:
        total += WEIGHTS["price"] / 2
        reasons.append("cena neuvedena")
    else:
        total += WEIGHTS["price"] * f
        mil = f"{price / 1_000_000:.2f}".replace(".", ",")
        reasons.append(f"cena {mil} mil. {_mark(f)}")

    usable = det.usable_area if det else None
    f = _range_fraction(usable, profile["usable_area"])
    if f is None:
        total += WEIGHTS["usable_area"] / 2
        reasons.append("užitná plocha neznámá")
    else:
        total += WEIGHTS["usable_area"] * f
        reasons.append(f"užitná {usable} m² {_mark(f)}")

    plot = (det.plot_area if det else None) or listing.get("area_m2")
    f = _range_fraction(plot, profile["plot_area"])
    if f is None:
        total += WEIGHTS["plot_area"] / 2
        reasons.append("pozemek neznámý")
    else:
        total += WEIGHTS["plot_area"] * f
        reasons.append(f"pozemek {_fmt_int(plot)} m² {_mark(f)}")

    rooms = det.rooms if det else None
    spec = profile["rooms"]
    if rooms is None:
        total += WEIGHTS["rooms"] / 2
    else:
        if spec["min"] <= rooms <= spec["max"]:
            f = 1.0
        elif spec["min"] - 1 <= rooms <= spec["max"] + 1:
            f = 0.5
        else:
            f = 0.0
        total += WEIGHTS["rooms"] * f
        label = det.disposition or f"{rooms} {'pokoj' if rooms == 1 else 'pokoje' if rooms < 5 else 'pokojů'}"
        reasons.append(f"{label} {_mark(f)}")

    if listing.get("location_id") in profile.get("city_location_ids", []):
        total += WEIGHTS["location"] / 3
        reasons.append("město ~")
    else:
        total += WEIGHTS["location"]
        reasons.append("obec ✓")

    return round(total), reasons
