"""Test end-to-end offline: dati demo -> cluster -> claim -> post (solo HTML)."""
import dataclasses
import json

from newsbot import pipeline
from newsbot.config import Settings
from newsbot.demo import seed_demo


def _ctx(tmp_path):
    s = dataclasses.replace(Settings(), db_path=tmp_path / "t.db", output_dir=tmp_path / "out",
                            data_dir=tmp_path, anthropic_api_key=None, embedding_backend="tfidf")
    ctx = pipeline.build_context(s)
    seed_demo(ctx.db, ctx.profiles)
    return ctx


def test_full_pipeline_offline(tmp_path):
    ctx = _ctx(tmp_path)
    pipeline.run_process(ctx)
    outs = pipeline.run_generate(ctx, png=False)
    names = {(o.parent.name, o.name) for o in outs}
    assert ("politica", "versus") in names and ("tech", "digest") in names
    for o in outs:
        assert (o / "slide_1.html").exists() and (o / "caption.txt").exists()
        assert json.loads((o / "fonti.json").read_text())        # ogni post ha le fonti
        assert (o / "DA_CONTROLLARE.txt").exists()               # senza LLM deve avvisare


def test_versus_is_symmetric_and_flags_missing_factcheck(tmp_path):
    ctx = _ctx(tmp_path)
    pipeline.run_process(ctx, ["politica"])
    (out,) = pipeline.run_generate(ctx, ["politica"], ["versus"], png=False)
    plan = json.loads((out / "plan.json").read_text())
    versus = next(s for s in plan["slides"] if s["type"] == "versus")
    assert versus["left"]["party"] == "FdI" and versus["right"]["party"] == "PD"
    assert any(s["type"] == "factcheck" for s in plan["slides"])
