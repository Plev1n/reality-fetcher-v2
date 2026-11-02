"""Convert the cadastre form (plain text fields) to the favourite's `katastr` dict and back."""

from __future__ import annotations

import re

FIELDS = ("obec", "ku_code", "ku_name", "lv", "parcels", "owners", "restrictions", "other_entries", "price_records")


def _lines(text: str) -> list[str]:
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


def _int_field(form: dict, key: str) -> int | None:
    raw = (form.get(key) or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise ValueError(f"Pole {key} musí být číslo (zadáno „{raw}“)")
    return int(raw)


def _keyed(text: str) -> list[tuple[str, str]]:
    out = []
    for line in _lines(text):
        if ":" not in line:
            raise ValueError(f"Řádek „{line}“ musí mít tvar „parcela: hodnota“")
        k, v = line.split(":", 1)
        out.append((k.strip(), v.strip()))
    return out


def katastr_from_form(form: dict) -> dict | None:
    """Return the katastr dict, or None when the form is empty. Raises ValueError on bad input."""
    if not any((form.get(f) or "").strip() for f in FIELDS):
        return None
    restrictions: dict[str, list[str]] = {}
    for parcel, value in _keyed(form.get("restrictions", "")):
        restrictions.setdefault(parcel, []).extend(v.strip() for v in value.split(";") if v.strip())
    price_records = {}
    for parcel, value in _keyed(form.get("price_records", "")):
        if not value.isdigit():
            raise ValueError(f"Cenové údaje u parcely {parcel} musí být číslo")
        price_records[parcel] = int(value)
    return {
        "obec": (form.get("obec") or "").strip() or None,
        "ku_code": _int_field(form, "ku_code"),
        "ku_name": (form.get("ku_name") or "").strip() or None,
        "lv": _int_field(form, "lv"),
        "parcels": [p.strip() for p in re.split(r"[,\n]", form.get("parcels") or "") if p.strip()],
        "owners": _lines(form.get("owners", "")),
        "restrictions": restrictions,
        "other_entries": _lines(form.get("other_entries", "")),
        "price_records": price_records,
    }


def katastr_to_form(kat: dict | None) -> dict[str, str]:
    kat = kat or {}
    return {
        "obec": kat.get("obec") or "",
        "ku_code": str(kat.get("ku_code") or ""),
        "ku_name": kat.get("ku_name") or "",
        "lv": str(kat.get("lv") or ""),
        "parcels": ", ".join(kat.get("parcels") or []),
        "owners": "\n".join(kat.get("owners") or []),
        "restrictions": "\n".join(f"{p}: {'; '.join(v)}" for p, v in (kat.get("restrictions") or {}).items()),
        "other_entries": "\n".join(kat.get("other_entries") or []),
        "price_records": "\n".join(f"{p}: {n}" for p, n in (kat.get("price_records") or {}).items()),
    }
