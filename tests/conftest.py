from datetime import datetime, timedelta, timezone

import pytest

from newsbot.models import Article


@pytest.fixture
def make_article():
    counter = {"n": 0}

    def _make(title, source="ansa", weight=1.0, hours_ago=1, summary="", kind="news", party=None, engagement=0.0):
        counter["n"] += 1
        return Article(
            id=counter["n"], url=f"https://ex.org/{counter['n']}", profile="t", source_id=source,
            source_name=source.upper(), kind=kind, party=party, title=title, summary=summary, text="",
            lang="it", weight=weight, published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
            engagement=engagement,
        )
    return _make
