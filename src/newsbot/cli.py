"""Riga di comando:  python -m newsbot <comando>   (oppure `newsbot <comando>`)"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys

from newsbot import pipeline
from newsbot.config import Settings
from newsbot.fetchers import fetch_source, make_client


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpcore", "urllib3", "trafilatura", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _profiles_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--profile", action="append", dest="profiles",
                   help="profilo (ripetibile). Default: tutti")


def cmd_init(args, settings: Settings) -> None:
    for d in (settings.data_dir / "manual", settings.data_dir / "programs", settings.output_dir):
        d.mkdir(parents=True, exist_ok=True)
    pipeline.build_context(settings)
    print(f"Database pronto: {settings.db_path}")
    print("Prossimo passo: copia .env.example in .env e prova `python -m newsbot demo`")


def cmd_check_sources(args, settings: Settings) -> None:
    ctx = pipeline.build_context(settings)
    with make_client(settings) as client:
        for p in pipeline.select_profiles(ctx, args.profiles):
            for src in p.sources:
                if not src.enabled:
                    print(f"SKIP  [{p.id}] {src.id:<16} disattivata in sources.yaml")
                    continue
                try:
                    items = fetch_source(src, settings, client)
                    newest = max((i["published_at"] for i in items), default=None)
                    print(f"OK    [{p.id}] {src.id:<16} {len(items):>3} elementi, ultimo: {newest}")
                except Exception as exc:  # noqa: BLE001
                    print(f"ERROR [{p.id}] {src.id:<16} {type(exc).__name__}: {exc}")


def cmd_discover(args, settings):
    from newsbot.fetchers.discover import discover_feeds
    with make_client(settings) as client:
        found = discover_feeds(args.url, client)
    if not found:
        print("Nessun feed trovato. Il sito potrebbe non averlo o bloccare i bot: usa l'import manuale.")
        return
    print("Feed funzionanti (copia l'url in config/sources.yaml):")
    for f in found:
        print(f"  {f['items']:>3} voci  {f['url']}   ({f['how']})")


def cmd_clusters(args, settings):
    """Mostra i cluster di oggi: serve a controllare che il raggruppamento abbia senso."""
    from newsbot.pipeline import day_of
    from newsbot.utils import utcnow
    ctx = pipeline.build_context(settings)
    day = day_of(utcnow())
    for p in pipeline.select_profiles(ctx, args.profiles):
        print(f"\n=== {p.id} ===")
        for c in ctx.db.load_clusters(p.id, day)[:15]:
            print(f"{c.score:5.2f}  {c.n_sources} fonti  {len(c.articles)} art | {c.title[:90]}")
            if len(c.articles) > 1:
                for a in c.articles:
                    print(f"          - {a.source_name}: {a.title[:80]}")


def cmd_fetch(args, settings):
    pipeline.run_fetch(pipeline.build_context(settings), args.profiles)


def cmd_manual(args, settings):
    from newsbot.fetchers.manual import import_manual
    ctx = pipeline.build_context(settings)
    n = import_manual(ctx.db, settings.data_dir / "manual", set(ctx.profiles))
    print(f"importati {n} elementi da {settings.data_dir / 'manual'}")


def cmd_programs(args, settings):
    pipeline.run_programs(pipeline.build_context(settings))


def cmd_process(args, settings):
    pipeline.run_process(pipeline.build_context(settings), args.profiles)


def cmd_generate(args, settings):
    ctx = pipeline.build_context(settings)
    pipeline.run_generate(ctx, args.profiles, [args.type] if args.type else None, png=not args.no_png)


def cmd_review(args, settings):
    ctx = pipeline.build_context(settings)
    from newsbot.pipeline import day_of, output_path
    from newsbot.utils import utcnow
    day = day_of(utcnow())
    outs = []
    for p in pipeline.select_profiles(ctx, args.profiles):
        for t in p.post_types:
            path = output_path(ctx, day, p.id, t)
            if path.exists():
                outs.append(path)
    pipeline.run_review(ctx, outs)


def cmd_run(args, settings):
    ctx = pipeline.build_context(settings)
    pipeline.run_fetch(ctx, args.profiles)
    pipeline.run_process(ctx, args.profiles)
    outs = pipeline.run_generate(ctx, args.profiles, png=not args.no_png)
    if args.review:
        pipeline.run_review(ctx, outs)


def cmd_demo(args, settings: Settings):
    """Pipeline completa su dati fittizi, in un DB e in una cartella separati."""
    from newsbot.demo import seed_demo
    demo = dataclasses.replace(
        settings, db_path=settings.data_dir / "demo.db", output_dir=settings.output_dir / "demo",
        anthropic_api_key=settings.anthropic_api_key if args.with_llm else None,
        llm_api_key=settings.llm_api_key if args.with_llm else None)
    if demo.db_path.exists():
        demo.db_path.unlink()
    ctx = pipeline.build_context(demo)
    seed_demo(ctx.db, ctx.profiles)
    pipeline.run_process(ctx, args.profiles)
    outs = pipeline.run_generate(ctx, args.profiles, png=not args.no_png)
    print(f"\nFatto. Apri l'anteprima, ad esempio:\n  {outs[0] / 'preview.html' if outs else demo.output_dir}")


def cmd_posts(args, settings):
    ctx = pipeline.build_context(settings)
    for r in ctx.db.list_posts():
        print(f"#{r['id']:<4} {r['day']} {r['profile']:<9} {r['post_type']:<7} {r['status']:<9} {r['output_dir']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="newsbot", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="crea cartelle e database").set_defaults(fn=cmd_init)

    s = sub.add_parser("check-sources", help="prova tutte le fonti e mostra quelle rotte")
    _profiles_arg(s); s.set_defaults(fn=cmd_check_sources)

    s = sub.add_parser("fetch", help="scarica le fonti (RSS, siti, social) + import manuale")
    _profiles_arg(s); s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("clusters", help="mostra i cluster di oggi")
    _profiles_arg(s); s.set_defaults(fn=cmd_clusters)

    s = sub.add_parser("discover", help="cerca i feed RSS di un sito")
    s.add_argument("url", help="es. https://www.ilfattoquotidiano.it")
    s.set_defaults(fn=cmd_discover)

    sub.add_parser("manual", help="importa data/manual/*.csv").set_defaults(fn=cmd_manual)
    sub.add_parser("programs", help="indicizza data/programs/*").set_defaults(fn=cmd_programs)

    s = sub.add_parser("process", help="clustering + ranking + estrazione claim")
    _profiles_arg(s); s.set_defaults(fn=cmd_process)

    s = sub.add_parser("generate", help="genera i post (piano + slide + caption)")
    _profiles_arg(s)
    s.add_argument("--type", choices=["digest", "versus"], help="solo questo tipo di post")
    s.add_argument("--no-png", action="store_true", help="solo HTML, senza screenshot")
    s.set_defaults(fn=cmd_generate)

    s = sub.add_parser("review", help="invia le bozze di oggi su Telegram")
    _profiles_arg(s); s.set_defaults(fn=cmd_review)

    s = sub.add_parser("run", help="fetch + process + generate (+ review)")
    _profiles_arg(s)
    s.add_argument("--review", action="store_true", help="a fine corsa invia su Telegram")
    s.add_argument("--no-png", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("demo", help="prova tutto su dati fittizi (offline)")
    _profiles_arg(s)
    s.add_argument("--with-llm", action="store_true", help="usa l'API Claude anche sui dati demo")
    s.add_argument("--no-png", action="store_true")
    s.set_defaults(fn=cmd_demo)

    sub.add_parser("posts", help="elenca i post generati").set_defaults(fn=cmd_posts)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    args.fn(args, Settings.from_env())


if __name__ == "__main__":
    main(sys.argv[1:])
