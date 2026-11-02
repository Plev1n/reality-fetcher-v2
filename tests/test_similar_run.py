import asyncio
import json
from pathlib import Path

from src.similar.details import ListingDetails, details_to_dict
from src.similar.run import mark_notified, select_candidates, update_similar, validate_profile

PROFILE = json.loads((Path(__file__).parent.parent / "config" / "profiles.json").read_text())[0]


def _l(id_, price=5500000, loc="przno", status="active", typ="dum", area=1375):
    return {"id": id_, "type": typ, "price": price, "location_id": loc, "location": loc,
            "status": status, "area_m2": area, "title": f"Dům {id_}", "url": f"https://x/{id_}",
            "portal": "idnes", "added": "2026-11-01", "price_history": []}


def _good(url):
    return ListingDetails(url=url, fetched="2026-11-02", usable_area=130, plot_area=1300, rooms=5)


def test_select_candidates_filters():
    data = {"listings": [
        _l("a"), _l("b", status="removed"), _l("c", typ="pozemek"),
        _l("d", price=9_000_000), _l("e", price=None),
    ]}
    ids = [x["id"] for x in select_candidates(data, PROFILE)]
    assert ids == ["a", "e"]


def test_fetch_failure_keeps_candidate():
    calls = []

    async def failing(url, client):
        calls.append(url)
        raise RuntimeError("boom")

    cache = {}
    res = asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, cache, {}, fetcher=failing, delay=0))
    assert [m["id"] for m in res["matches"]] == ["a"]
    assert res["matches"][0]["details"] is None
    assert cache["a"]["ok"] is False
    # same day: failure is cached, no second fetch
    asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, cache, {}, fetcher=failing, delay=0))
    assert len(calls) == 1


def test_cached_details_not_refetched():
    async def never(url, client):
        raise AssertionError("should not fetch")

    cache = {"a": details_to_dict(_good("https://x/a"))}
    res = asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, cache, {}, fetcher=never, delay=0))
    assert res["matches"][0]["score"] >= 85


def test_new_ids_only_new_matches():
    async def good(url, client):
        return _good(url)

    prev = {"matches": [{"id": "a", "score": 95}], "notified_ids": ["a"]}
    res = asyncio.run(update_similar({"listings": [_l("a"), _l("b")]}, PROFILE, {}, prev, fetcher=good, delay=0))
    assert res["new_ids"] == ["b"]
    assert {m["id"]: m["new"] for m in res["matches"]} == {"a": False, "b": True}
    assert res["notified_ids"] == ["a"]  # b only after a successful email
    mark_notified(res)
    assert res["notified_ids"] == ["a", "b"]


def test_first_run_is_baseline_without_new():
    async def good(url, client):
        return _good(url)

    res = asyncio.run(update_similar({"listings": [_l("a"), _l("b"), _l("c")]}, PROFILE, {}, {},
                                     fetcher=good, max_fetch=2, delay=0))
    assert res["new_ids"] == []
    assert res["notified_ids"] == ["a", "b", "c"]  # c has no details yet, still baseline


def test_price_alone_is_not_a_match():
    async def failing(url, client):
        raise RuntimeError("x")

    prev = {"matches": [], "notified_ids": []}
    res = asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, {}, prev, fetcher=failing, delay=0))
    m = res["matches"][0]
    assert m["score"] >= 60 and m["match"] is False and res["new_ids"] == []


def test_dipping_below_threshold_does_not_renotify():
    async def good(url, client):
        return _good(url)

    prev = {"matches": [], "notified_ids": ["a"]}
    res = asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, {}, prev, fetcher=good, delay=0))
    assert res["new_ids"] == []


def test_agent_name_not_in_public_details():
    async def good(url, client):
        d = _good(url)
        d.agent = "Jana Smyšlená"
        return d

    res = asyncio.run(update_similar({"listings": [_l("a")]}, PROFILE, {}, {}, fetcher=good, delay=0))
    assert "agent" not in res["matches"][0]["details"]


def test_validate_profile_slug_collision():
    import pytest
    with pytest.raises(ValueError):
        validate_profile({"slug": "fm"}, {"fm", "poruba"})
    validate_profile({"slug": "podobne"}, {"fm", "poruba"})


def test_max_fetch_limit():
    fetched = []

    async def good(url, client):
        fetched.append(url)
        return _good(url)

    listings = [_l(str(i)) for i in range(5)]
    asyncio.run(update_similar({"listings": listings}, PROFILE, {}, {}, fetcher=good, max_fetch=2, delay=0))
    assert len(fetched) == 2


def test_matches_sorted_and_threshold_flag():
    async def good(url, client):
        return _good(url)

    listings = [_l("city", loc="frydek_mistek", price=6_900_000), _l("best")]
    res = asyncio.run(update_similar({"listings": listings}, PROFILE, {}, {"matches": []}, fetcher=good, delay=0))
    assert res["matches"][0]["id"] == "best"
    assert all("match" in m for m in res["matches"])
