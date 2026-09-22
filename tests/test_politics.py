from newsbot.config import Settings, load_themes
from newsbot.politics.claims import _valid_quote, heuristic_theme
from newsbot.politics.programs import chunk_text


def test_heuristic_theme_finds_sanita():
    themes = load_themes(Settings())
    assert heuristic_theme("Più fondi per ospedali e liste d'attesa nella sanità", themes) == "sanita"


def test_quote_must_appear_in_source():
    src = "Il partito ha dichiarato che aumenteremo i fondi per la sanità pubblica entro l'anno."
    assert _valid_quote("aumenteremo i fondi per la sanità pubblica", src)
    assert _valid_quote("una frase inventata dal modello", src) is None


def test_quote_longer_than_15_words_is_dropped():
    src = " ".join(f"parola{i}" for i in range(30))
    assert _valid_quote(" ".join(f"parola{i}" for i in range(16)), src) is None


def test_chunk_text_respects_size():
    text = "\n\n".join(["frase " * 60] * 6)
    chunks = chunk_text(text, size=500)
    assert chunks and all(len(c) <= 500 for c in chunks)


def test_find_feed_links_reads_html_head():
    from newsbot.fetchers.discover import find_feed_links
    html = ('<head><link rel="alternate" type="application/rss+xml" title="x" href="/feed/">'
            '<link rel="stylesheet" href="/a.css"></head>')
    assert find_feed_links(html, "https://ex.org/") == ["https://ex.org/feed/"]
