from src.scrapers import import_all_scrapers, SCRAPERS


def test_all_scrapers_import():
    import_all_scrapers()
    assert len(SCRAPERS) == 18


def test_idnes_card_parse():
    from src.scrapers.idnes import _parse_card, HTMLParser
    html = """<div class="c-products__inner">
      <a class="c-products__link" href="/detail/prodej/dum/przno/abc/">
      <h2 class="c-products__title">Prodej domu 135 m² s pozemkem 1 375 m²</h2></a>
      <p class="c-products__info">Pržno, okres Frýdek-Místek</p>
      <p class="c-products__price">5 500 000 Kč</p></div>"""
    card = HTMLParser(html).css_first("div.c-products__inner")
    raw = _parse_card(card, "dum")
    assert raw.portal_id == "abc"
    assert raw.area_raw == "1 375 m2"
    assert raw.url == "https://reality.idnes.cz/detail/prodej/dum/przno/abc/"


def test_idnes_title_keeps_word_spacing():
    from src.scrapers.idnes import _parse_card, HTMLParser
    html = """<div class="c-products__inner"><a class="c-products__link" href="/detail/prodej/dum/x/abc/">
      <h2 class="c-products__title"><span class="u-hidden">prodej</span>domu 135 m²</h2></a></div>"""
    raw = _parse_card(HTMLParser(html).css_first("div.c-products__inner"), "dum")
    assert raw.title == "prodej domu 135 m²"
