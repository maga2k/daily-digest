"""Verifica la logica che usa l'LLM con un finto client (nessuna chiamata di rete)."""
import dataclasses

from newsbot import pipeline
from newsbot.config import Settings
from newsbot.demo import seed_demo
from newsbot.llm.client import parse_json
from newsbot.posts.digest import plan_digest


class FakeLLM:
    enabled = True

    def __init__(self, payload):
        self.payload = payload

    def json(self, system, user, max_tokens=2000, retries=1):
        return self.payload


def test_parse_json_tolerates_fences():
    assert parse_json('Ecco:\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_digest_uses_llm_output_and_matches_by_cluster_id(tmp_path):
    s = dataclasses.replace(Settings(), db_path=tmp_path / "t.db", output_dir=tmp_path / "o",
                            data_dir=tmp_path, anthropic_api_key=None, embedding_backend="tfidf")
    ctx = pipeline.build_context(s)
    seed_demo(ctx.db, ctx.profiles)
    pipeline.run_process(ctx, ["tech"])
    from newsbot.pipeline import day_of
    from newsbot.utils import utcnow
    clusters = ctx.db.load_clusters("tech", day_of(utcnow()))
    payload = {"hook": "Hook di prova", "caption": "Caption di prova",
               "stories": [{"cluster_id": clusters[0].id, "headline": "Titolo LLM", "bullets": ["uno", "due"],
                            "framing": None, "note": "benchmark non verificati"}]}
    plan = plan_digest(ctx.profiles["tech"], clusters, FakeLLM(payload), "2026-09-19")
    story = next(sl for sl in plan.slides if sl["type"] == "story")
    assert story["headline"] == "Titolo LLM" and story["note"] == "benchmark non verificati"
    assert plan.slides[0]["title"] == "Hook di prova"
    assert not any("LLM non configurato" in w for w in plan.warnings)


def test_invalid_llm_output_falls_back(tmp_path):
    s = dataclasses.replace(Settings(), db_path=tmp_path / "t.db", data_dir=tmp_path,
                            anthropic_api_key=None, embedding_backend="tfidf")
    ctx = pipeline.build_context(s)
    seed_demo(ctx.db, ctx.profiles)
    pipeline.run_process(ctx, ["tech"])
    from newsbot.pipeline import day_of
    from newsbot.utils import utcnow
    clusters = ctx.db.load_clusters("tech", day_of(utcnow()))
    plan = plan_digest(ctx.profiles["tech"], clusters, FakeLLM({"boh": 1}), "2026-09-19")
    assert plan is not None and any("non valida" in w for w in plan.warnings)
