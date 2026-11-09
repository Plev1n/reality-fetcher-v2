from src.market.segment import monthly, segment_listings, snapshot, update_history, usable_area

SEG = {
    "slug": "segment_przno",
    "type": "dum",
    "price": {"min": 4_000_000, "max": 7_000_000},
    "usable_area": {"min": 100, "max": 160},
    "plot_min": 900,
    "watch_ids": ["w1"],
}


def _l(id_, price=5_000_000, area=1200, title="Prodej rodinného domu 120 m², pozemek 1200 m²",
       status="active", typ="dum", added="2026-11-01", history=None):
    return {"id": id_, "type": typ, "price": price, "area_m2": area, "title": title, "status": status,
            "added": added, "price_history": history or [{"date": added, "price": price}]}


def test_usable_area_prefers_cache_then_title():
    cache = {"a": {"ok": True, "usable_area": 135}}
    assert usable_area(_l("a"), cache) == 135
    assert usable_area(_l("b"), {}) == 120
    assert usable_area(_l("c", title="Rodinný dům Baška"), {}) is None
    # failed cache entry falls back to the title
    assert usable_area(_l("d"), {"d": {"ok": False, "usable_area": 999}}) == 120


def test_segment_filters_type_price_area_plot_status():
    data = {"listings": [
        _l("ok"),
        _l("removed", status="removed"),
        _l("land", typ="pozemek"),
        _l("cheap", price=3_000_000),
        _l("small_plot", area=800),
        _l("big_house", title="Prodej rodinného domu 250 m², pozemek 1200 m²"),
        _l("unknown_area", title="Rodinný dům"),
        _l("no_price", price=None),
    ]}
    ids = sorted(x["listing"]["id"] for x in segment_listings(data, {}, SEG))
    # unknown usable area stays in (counted for price stats), out-of-range area is dropped
    assert ids == ["ok", "unknown_area"]


def test_snapshot_stats():
    data = {"listings": [
        _l("a", price=4_000_000, title="Prodej rodinného domu 100 m², pozemek 1000 m²"),
        _l("b", price=5_250_000, title="Prodej rodinného domu 125 m², pozemek 1000 m²",
           history=[{"date": "2026-10-01", "price": 5_500_000}, {"date": "2026-11-05", "price": 5_250_000}]),
        _l("c", price=6_000_000, title="Rodinný dům", added="2026-09-01"),
        _l("w1", price=5_500_000, title="Prodej rodinného domu 135 m², pozemek 1375 m²"),
    ]}
    cache = {"a": {"ok": True, "usable_area": 100, "condition": "před rekonstrukcí"}}
    s = snapshot(data, cache, SEG, "2026-11-09")
    assert s["date"] == "2026-11-09"
    assert s["count"] == 4
    assert s["count_with_area"] == 3
    assert s["median_price"] == 5_375_000
    assert s["median_ppm"] == 40_741  # median of 40 000, 40 740.7, 42 000
    assert s["price_cuts"] == 1
    assert s["new_30d"] == 3
    assert s["median_ppm_before_renovation"] == 40_000
    assert s["watch"] == {"w1": 5_500_000}


def test_snapshot_watch_missing_is_none():
    s = snapshot({"listings": []}, {}, SEG, "2026-11-09")
    assert s["count"] == 0 and s["median_ppm"] is None and s["watch"] == {"w1": None}


def test_update_history_replaces_same_day_and_sorts():
    h = {"snapshots": [{"date": "2026-11-09", "count": 1}, {"date": "2026-11-01", "count": 5}]}
    update_history(h, {"date": "2026-11-09", "count": 2})
    update_history(h, {"date": "2026-11-10", "count": 3})
    assert [(s["date"], s["count"]) for s in h["snapshots"]] == [
        ("2026-11-01", 5), ("2026-11-09", 2), ("2026-11-10", 3)]


def test_monthly_takes_last_snapshot_of_month():
    snaps = [{"date": "2026-11-01", "count": 1}, {"date": "2026-11-30", "count": 2},
             {"date": "2026-12-02", "count": 3}]
    assert monthly(snaps) == [{"date": "2026-11-30", "count": 2}, {"date": "2026-12-02", "count": 3}]


def test_snapshot_keeps_listing_prices_for_diffing():
    data = {"listings": [_l("a"), _l("b", price=6_000_000)]}
    s = snapshot(data, {}, SEG, "2026-11-09")
    assert s["listings"] == {"a": 5_000_000, "b": 6_000_000}


def test_district_area_data_from_sreality_raws():
    from src.market.segment import district_area_data
    from src.models import RawListing

    def raw(id_, sub, title, price):
        return RawListing(portal="sreality", portal_id=id_, title=title,
                          url=f"https://www.sreality.cz/detail/prodej/dum/{sub}/x/{id_}",
                          price_raw=f"{price} Kc" if price else None,
                          area_raw=None)

    data = district_area_data([
        raw("1", "rodinny", "Prodej rodinného domu 135 m², pozemek 1 375 m²", 5_500_000),
        raw("2", "chata", "Prodej chaty 40 m², pozemek 500 m²", 1_500_000),
        raw("3", "vila", "Prodej vily 150 m², pozemek 1000 m²", None),
    ])
    ls = {l["id"]: l for l in data["listings"]}
    assert set(ls) == {"sreality_1", "sreality_3"}
    assert ls["sreality_1"]["price"] == 5_500_000
    assert ls["sreality_1"]["area_m2"] == 1375
    assert ls["sreality_1"]["status"] == "active" and ls["sreality_1"]["type"] == "dum"
    assert ls["sreality_3"]["price"] is None
