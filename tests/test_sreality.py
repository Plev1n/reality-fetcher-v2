from src.scrapers.sreality import parse_estate


def test_parse_v1_estate():
    estate = {
        "advert_name": "Prodej rodinného domu 110 m², pozemek 1198 m²",
        "hash_id": 123,
        "price_czk": 5990000.0,
        "category_main_cb": {"name": "Domy", "value": 2},
        "category_type_cb": {"name": "Prodej", "value": 1},
        "category_sub_cb": {"name": "Rodinný", "value": 37},
        "locality": {"city": "Baška", "citypart": "Kunčičky u Bašky",
                     "city_seo_name": "baska", "gps_lat": 49.64, "gps_lon": 18.36},
        "advert_images": ["//d18-a.sdn.cz/x.jpeg"],
    }
    raw = parse_estate(estate, "dum")
    assert raw.portal_id == "123"
    assert raw.url == "https://www.sreality.cz/detail/prodej/dum/rodinny/baska/123"
    assert raw.location_raw == "Baška - Kunčičky u Bašky"
    assert raw.price_raw == "5990000 Kc"
    assert raw.area_raw == "1198 m2"
    assert raw.coordinates == (49.64, 18.36)
    assert raw.images == ["https://d18-a.sdn.cz/x.jpeg"]


def test_pagination_without_total_continues(monkeypatch):
    import asyncio
    from src.scrapers import sreality

    pages = []

    class Resp:
        def __init__(self, n): self.n = n
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"hash_id": self.n * 100 + i + 1, "advert_name": "x"} for i in range(60 if self.n < 2 else 3)]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, params):
            pages.append(params["offset"])
            return Resp(len(pages) - 1)

    s = sreality.SrealityScraper()
    monkeypatch.setattr(s, "_get_client", lambda: Client())
    async def nodelay(): pass
    monkeypatch.setattr(s, "_delay", nodelay)
    out = asyncio.run(s.scrape("dum"))
    assert pages == [0, 60, 120] and len(out) == 123
