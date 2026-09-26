# newsbot

A bot that pulls news from multiple sources, clusters them by event, ranks them, and drafts
**Instagram carousel posts** (PNG slides + caption + sources) for **human review**. No
auto-publishing. It can also produce a longer-form write-up for **Telegram**, meant as a deeper
follow-up to the short Instagram version (e.g. for a separate, possibly paid, channel).

**This project targets an Italian-speaking audience.** All prompts, generated captions, source
lists and the `politica` profile are built around Italian news and Italian politics; the code and
this README are in English, everything the bot *writes* is in Italian.

Built-in profiles: `mondo` (world news), `politica` (Italian politics, with claim extraction and
fact-check linking), `scienza` (science/health), `economia` (economy/finance), `tech`. Adding a
new one is just a config entry in `config/profiles.yaml` + `config/sources.yaml` — see
"Adding a profile" below.

\```
sources (RSS / sites / social)  ->  SQLite  ->  clustering by event  ->  ranking
      -> [politica] per-party claims + third-party fact-checks + party program excerpts
      -> LLM: slide text + caption, or a long-form Telegram write-up
      -> HTML/CSS -> PNG  ->  output/  (+ optional Telegram delivery for review)
\```

## Example output

## Example output

See [`examples/`](examples/) for a real, dated snapshot of the pipeline's output across the
`mondo`, `economia` and `politica` profiles (digest + deepdive for each) — reviewed by hand before
being committed. For a fictional dataset you can regenerate yourself risk-free, run `python -m
newsbot demo` (see "Quick start" below).

## Quick start (VS Code)

\```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"              # base install, lightweight
python -m playwright install chromium   # needed to render PNG slides
cp .env.example .env

python -m newsbot demo               # runs the whole pipeline on FAKE data, no network, no keys needed
\```

Then open `output/demo/<date>/<profile>/<post-type>/preview.html`. The same actions are wired up
in VS Code's **Run and Debug** (F5) and **Tasks** (`.vscode/`).

For better clustering (matching Italian/English titles about the same event), install local
multilingual embeddings:
\```bash
pip install -e ".[ml]"               # sentence-transformers, ~2 GB with torch
\```
Without it, the bot falls back to TF-IDF — fine for a first try, but it won't match titles across
languages.

## Real usage

\```bash
python -m newsbot check-sources           # see which feeds actually work (URLs change over time!)
python -m newsbot run -p tech             # fetch + process + generate for one profile
python -m newsbot deepdive -p politica    # long-form write-up, saved for review (not sent yet)
python -m newsbot deepdive -p politica --send   # ...and send it to Telegram
python -m newsbot run --review            # all profiles + push drafts to Telegram
\```

`scripts/morning.sh` runs `run` + `clusters` for a fixed list of profiles in sequence, logging to
`logs/`, and keeps going if one profile fails. Edit the `PROFILES=(...)` line to your liking.

Other commands: `fetch`, `manual`, `programs`, `process`, `generate [--type digest|versus]`,
`review`, `posts`, `clusters -p <profile>` (inspect today's clusters), `discover <site-url>`
(find a site's RSS feed).

Without an LLM configured, the bot runs in **heuristic mode**: no calls out, first-sentence
summaries instead of rewritten prose, and every output folder gets a `DA_CONTROLLARE.txt`
("to review") flagging what it had to fall back on. Nothing is ever silently empty.

## LLM providers

The pipeline supports two backends:

- **Anthropic** (`ANTHROPIC_API_KEY` in `.env`) — no permanent free tier, but the best
  quality/JSON-reliability tradeoff, especially for the `politica` profile's claim extraction.
- **Any OpenAI-compatible endpoint** (`NEWSBOT_LLM_PROVIDER=openai_compatible` +
  `NEWSBOT_LLM_API_KEY` + `NEWSBOT_LLM_BASE_URL` + `NEWSBOT_MODEL`) — this covers **Groq** (free
  tier, fast, hosts Llama/Qwen), **OpenRouter**, **Google Gemini**, and **Ollama** running fully
  locally on your own machine. Install with `pip install -e ".[free-llm]"`.

Example `.env` for Groq:
\```
NEWSBOT_LLM_PROVIDER=openai_compatible
NEWSBOT_LLM_API_KEY=gsk_...
NEWSBOT_LLM_BASE_URL=https://api.groq.com/openai/v1
NEWSBOT_MODEL=llama-3.3-70b-versatile   # check what your account actually has access to: GET /openai/v1/models
\```

Free/open models are noticeably weaker on strict JSON output and on Italian prose quality than
Anthropic's models — the code degrades gracefully when a response can't be parsed (same
`DA_CONTROLLARE.txt` mechanism), but for the `politica` profile specifically (claim extraction,
quote validation) a stronger model is worth the cost once you're past prototyping.

## Structure

\```
config/
  profiles.yaml    profiles: ranking weights, style, prompts, parties to compare, hashtags
  sources.yaml     sources per profile (type, weight/authority, party, enabled flag)
  themes.yaml      CLOSED list of political topics + keywords (claim extraction only picks from this)
src/newsbot/
  cli.py           commands
  pipeline.py      fetch -> process -> generate -> deepdive -> review orchestration
  db.py            SQLite schema
  fetchers/        rss, web (trafilatura), apify (third-party social scraping), manual (CSV import),
                   discover (finds a site's RSS feed)
  processing/      embeddings, clustering, ranking, sentiment (optional)
  politics/        claims (per topic), factcheck (links to third-party verifications), programs
                   (party manifestos, chunked + searched by similarity)
  posts/           digest (top N stories), versus (party A vs B + fact-check + program),
                   deepdive (long-form Telegram write-up)
  llm/             Anthropic / OpenAI-compatible client + all prompts (prompts.py)
  render/          Jinja templates + CSS for the slides, Playwright screenshots
  delivery/        Telegram (review drafts, and the deepdive long-form message)
  demo.py          fictional data to try the whole thing offline
data/manual/       CSV files with hand-pasted social posts
data/programs/     party manifestos (PDF/txt) to index
assets/fonts/      your own fonts (see below)
scripts/morning.sh daily driver script
tests/             pytest, all run offline
\```

## How the `politica` profile works

1. **Party sources** (`kind: party`): party websites/social. In posts they always show up as
   "according to Party X", never as plain facts.
2. **Claims per topic**: the LLM extracts up to 3 claims per press release, picking only from the
   closed topic list in `themes.yaml`. Literal quotes are **validated** against the source text
   (must actually appear there, max 15 words) — anything else is dropped rather than risk a
   fabricated quote.
3. **Symmetric comparison**: for the topic with the most claims from *both* parties in
   `versus_parties`, the same prompt and the same length constraints are applied to each side.
4. **Third-party fact-checks** (`kind: factcheck`): matched by similarity and reported attributed
   ("According to Pagella Politica..."). If none are found, the slide/message says **"not
   verified"** — the bot never issues its own verdict.
5. **Party program excerpts**: if you've added manifestos under `data/programs/`, the closest
   matching excerpt is shown next to the current claims.
6. **`deepdive`**: reuses all of the above to write a longer, Telegram-formatted message instead
   of a slide — one section per party, one section for fact-checks (or "not verified"), sources at
   the end.

## Adding a profile

It's pure configuration — no code changes. `economia` (economy/finance) was added this way; look
at its blocks in `config/profiles.yaml` and `config/sources.yaml` as a template. In short: copy an
existing profile block, adjust `label`, `hashtags`, `style`, `ranking` weights and
`system_prompt`, then add a matching `sources:` list with real (verified!) RSS feeds.

## Social media (Instagram / X)

These are the hardest sources to get automatically: official APIs don't let you read *other*
accounts' posts (or charge for it), and direct scraping violates the platforms' terms. Three
options, easiest first:

1. **Manual import**: paste text into a CSV under `data/manual/` (format in
   `esempio.csv.example`), then run `manual`.
2. **Third-party scraper (Apify)**: uncomment the `apify_instagram` lines in `sources.yaml` and set
   `APIFY_TOKEN`. Check current pricing, the actor's exact schema, and the platform's terms — this
   is a legal gray area.
3. **X**: not implemented on purpose (the official API is paid and changes often). Extension point:
   `fetchers/apify.py`.

## Fonts and design

Slides are HTML/CSS (`src/newsbot/render/templates/`). Per-profile colors live in
`profiles.yaml -> style`. To use your own fonts: drop the files into `assets/fonts/` (e.g.
`Newsreader.woff2`) and set `font_serif: '"Newsreader", Georgia, serif'` in `style` (the name is
the filename without extension). Text auto-shrinks if it doesn't fit (`data-fit`).

## Things to know

- **Verify feed URLs** with `check-sources` and `discover <site>`: the ones in `sources.yaml` are
  a starting point, not guaranteed — sites change their RSS paths often, and some never had one.
  Broken sources are skipped without blocking the rest of the pipeline; `enabled: false` disables
  one without deleting the config.
- **Copyright**: the bot uses feed titles/summaries, rewrites them, and links back — never
  reproduces full articles. No stock photos of politicians pulled from the web.
- **Human review, always** — especially for `politica`. A bad claim there is your mistake, in
  public, not the code's.
- **Source bias is an editorial choice**: which sources you include and their `weight` in
  `sources.yaml` are decisions you're making, not neutral defaults. Make them explicit (the
  sources slide already lists them).
- **Cost**: clustering runs locally; the LLM only ever sees the top N clusters (roughly one call
  per digest, one per topic in `versus`, one per party press release for claim extraction).
- **robots.txt / ToS**: check them before turning on `type: web` or `fulltext: true` at any real
  frequency on a site you don't control.
- **AI content disclosure**: the `disclosure` field in each profile (shown on every caption) exists
  for a reason — keep it on once an LLM is generating the text, both because it's honest and
  because platform/regulatory rules increasingly expect it.

## Ideas for next steps

- Tune clustering thresholds (`Embedder.THRESHOLDS`) and ranking weights against real data, not demo data.
- Compare "what they say" against "how they vote", using Camera/Senato open data.
- Track topics over time (weekly trends, "rising" stories).
- Persistent embeddings cache; Postgres if volume grows.
- Instagram Stories format (1080×1920) from the same templates; Graph API upload after approval.
- Telegram inline buttons ("approve / discard / regenerate") that update `posts.status`.
- A paid Telegram channel/newsletter as a deeper follow-up to the free Instagram digest.