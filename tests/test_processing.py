from datetime import datetime, timezone

from newsbot.processing.clustering import cluster_articles
from newsbot.processing.embeddings import Embedder
from newsbot.processing.ranking import build_clusters, score_cluster


def test_similar_titles_are_grouped(make_article):
    arts = [
        make_article("Terremoto a Valdoria: crolli e centinaia di sfollati", "ansa"),
        make_article("Valdoria, il terremoto provoca crolli e sfollati", "bbc"),
        make_article("Il Parlamento approva la nuova legge sul turismo", "ansa"),
    ]
    groups = cluster_articles(arts, Embedder("tfidf"))
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_more_sources_rank_higher(make_article):
    now = datetime.now(timezone.utc)
    many = [make_article("evento A", s) for s in ("ansa", "bbc", "dw")]
    few = [make_article("evento B", "ansa")]
    assert score_cluster(many, now) > score_cluster(few, now)


def test_min_sources_filters(make_article):
    now = datetime.now(timezone.utc)
    groups = [[make_article("a", "x")], [make_article("b", "x"), make_article("b2", "y")]]
    clusters = build_clusters("t", groups, now, min_sources=2)
    assert len(clusters) == 1 and clusters[0].n_sources == 2


def test_recent_beats_old_at_equal_coverage(make_article):
    now = datetime.now(timezone.utc)
    fresh = [make_article("x", "ansa", hours_ago=1)]
    old = [make_article("y", "ansa", hours_ago=40)]
    assert score_cluster(fresh, now) > score_cluster(old, now)


def test_hn_boilerplate_does_not_glue_unrelated_posts(make_article):
    boiler = "Article URL: https://x.org Comments URL: https://news.ycombinator.com/item?id=1 Points: 10 # Comments: 2"
    arts = [make_article("Amiga Unix, Again", "hn", summary=boiler),
            make_article("What happened to the Snowden archive", "hn", summary=boiler),
            make_article("Qwen Image 2.1", "hn", summary=boiler)]
    assert len(cluster_articles(arts, Embedder("tfidf"))) == 3


def test_hn_points_become_engagement():
    from newsbot.fetchers.rss import _POINTS_RE
    assert _POINTS_RE.search("Points: 342\n# Comments: 80").group(1) == "342"


def test_exclude_patterns_from_config():
    import re

    from newsbot.config import Settings, load_profiles
    p = load_profiles(Settings())["tech"]
    rx = re.compile("|".join(p.exclude_title_patterns), re.I)
    assert rx.search("Factor Delivery Meals Review (2026)")
    assert rx.search("6 days left to save up to $200 to TechCrunch Disrupt 2026")
    assert not rx.search("Amazon doesn't trust Meta's Muse AI agent")
