# newsbot

Bot che raccoglie notizie da più fonti, le raggruppa per evento, le ordina e prepara **caroselli Instagram**
(slide PNG 1080×1350 + caption + fonti) per **revisione umana**. Nessuna pubblicazione automatica.

Profili inclusi: `mondo`, `politica`, `scienza`, `tech`. Per aggiungerne uno basta una voce in
`config/profiles.yaml` e le sue fonti in `config/sources.yaml`.

```
fonti (RSS / siti / social)  ->  SQLite  ->  clustering per evento  ->  ranking
      -> [politica] claim per partito + fact-check di terzi + programma
      -> LLM: testi slide + caption  ->  HTML/CSS -> PNG  ->  output/  (+ Telegram per revisione)
```

## Avvio rapido (VS Code)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"              # base, leggero
python -m playwright install chromium   # serve per i PNG
cp .env.example .env

python -m newsbot demo               # prova tutto su dati FITTIZI, senza rete né chiavi
```

Poi apri `output/demo/<data>/<profilo>/<tipo>/preview.html`. Le stesse azioni sono nei
**Run and Debug** (F5) e nei **Tasks** di VS Code (`.vscode/`).

Per il salto di qualità (clustering multilingua IT/EN) installa gli embeddings locali:

```bash
pip install -e ".[ml]"               # sentence-transformers, ~2 GB con torch
```

Senza, il bot usa TF-IDF: va bene per provare, ma non accoppia titoli in lingue diverse.

## Uso reale

```bash
python -m newsbot check-sources      # verifica quali feed funzionano (gli URL cambiano!)
python -m newsbot run -p tech        # fetch + process + generate per un profilo
python -m newsbot run --review       # tutti i profili + invio bozze su Telegram
```

Comandi singoli: `fetch`, `manual`, `programs`, `process`, `generate [--type digest|versus]`, `review`, `posts`.

Strumenti di diagnosi:
- `check-sources`: prova ogni fonte e spiega perché fallisce (HTTP, tipo di contenuto, blocchi).
- `discover https://sito.it`: trova i feed RSS di un sito.
- `clusters -p tech`: mostra i cluster di oggi, per controllare che il raggruppamento abbia senso.
- In `sources.yaml`, `enabled: false` disattiva una fonte; in `profiles.yaml`, `exclude_title_patterns` scarta titoli promozionali.

Senza `ANTHROPIC_API_KEY` il bot funziona in modalità euristica (utile per sviluppare); ogni post
generato così contiene un file `DA_CONTROLLARE.txt` che te lo segnala.

## Struttura

```
config/
  profiles.yaml    profili: ranking, stile, prompt, partiti da confrontare, hashtag
  sources.yaml     fonti per profilo (tipo, peso/autorevolezza, partito)
  themes.yaml      lista CHIUSA di temi politici + parole chiave
src/newsbot/
  cli.py           comandi
  pipeline.py      orchestrazione fetch -> process -> generate -> review
  db.py            schema SQLite
  fetchers/        rss, web (trafilatura), apify (social di terzi), manual (CSV)
  processing/      embeddings, clustering, ranking, sentiment (opzionale)
  politics/        claims (per tema), factcheck (link a verifiche di terzi), programs (programmi)
  posts/           digest (top N storie), versus (partito A vs B, fact-check, programma)
  llm/             client Anthropic + prompt (tutti in prompts.py)
  render/          template Jinja + CSS delle slide, screenshot Playwright
  delivery/        Telegram
  demo.py          dati fittizi per provare tutto offline
data/manual/       CSV con post social incollati a mano
data/programs/     programmi elettorali (PDF/txt) da indicizzare
assets/fonts/      i tuoi font (vedi sotto)
tests/             pytest (13 test, girano offline)
```

## Come funziona il profilo politica

1. **Fonti di parte** (`kind: party`): siti/social dei partiti. Nel post compaiono come "secondo FdI…", mai come fatti.
2. **Claim per tema**: l'LLM estrae fino a 3 affermazioni per comunicato, scegliendo solo dai temi di `themes.yaml`.
   Le citazioni letterali vengono **validate** (devono comparire nel testo, max 15 parole), altrimenti scartate.
3. **Confronto simmetrico**: per il tema con più claim di *entrambi* i partiti in `versus_parties`, stesso prompt e
   stessa lunghezza per ciascuno.
4. **Fact-check di terzi** (`kind: factcheck`): si cercano per similarità quelli già pubblicati e si riportano
   attribuiti ("Secondo Pagella Politica"). Se non ce ne sono, la slide dice **"Non verificato"**. Il bot non emette verdetti.
5. **Programma**: se hai messo i programmi in `data/programs/`, la slide "Cosa c'era nel programma" mostra il passaggio più vicino.

## Social (Instagram / X)

Sono le fonti più difficili: le API ufficiali non permettono di leggere profili altrui (o costano), lo scraping diretto
viola i ToS. Tre strade, dalla più semplice:

1. **Import manuale**: incolla i testi in un CSV in `data/manual/` (formato in `esempio.csv.example`) e lancia `manual`.
2. **Scraper di terzi (Apify)**: decommenta le righe `apify_instagram` in `sources.yaml` e imposta `APIFY_TOKEN`.
   Verifica costi, attore e ToS: è zona grigia.
3. **X**: non implementato di proposito (API a pagamento e in continuo cambiamento). Punto di estensione: `fetchers/apify.py`.

## Font e grafica

Le slide sono HTML/CSS (`src/newsbot/render/templates/`). Colori per profilo in `profiles.yaml → style`.
Per usare font tuoi: copia i file in `assets/fonts/` (es. `Newsreader.woff2`) e in `style` metti
`font_serif: '"Newsreader", Georgia, serif'` (il nome è quello del file senza estensione).
Il testo si rimpicciolisce da solo se non entra nella slide (`data-fit`).

## Da sapere

- **Verifica gli URL dei feed** con `check-sources`: quelli in `sources.yaml` sono un punto di partenza, non garantiti.
  Le fonti che falliscono vengono saltate senza bloccare le altre.
- **Copyright**: si usano titoli e sommari dei feed; riassumi e linka, non riprodurre articoli. Niente foto di politici prese dal web.
- **Revisione umana sempre**: sui contenuti politici un errore del bot è un errore tuo, pubblico.
- **Bias delle fonti**: la scelta e i `weight` in `sources.yaml` sono decisioni editoriali. Rendile esplicite (ultima slide).
- **Costi**: si clusterizza in locale e l'LLM lavora solo sui top N cluster (1 chiamata per digest, 1 per tema nel versus, 1 per comunicato per i claim).
- **Robots.txt/ToS** dei siti dei partiti: controllali prima di attivare `type: web` o `fulltext: true` con frequenza alta.

## Idee per i prossimi passi

- Tuning soglie di clustering (`Embedder.THRESHOLDS`) e dei pesi di ranking con dati veri.
- Confronto con le **votazioni** (open data Camera/Senato): "cosa dicono" vs "come votano".
- Storico dei temi (trend settimanale) e rilevamento di storie "in crescita".
- Cache persistente degli embeddings; Postgres se cresce il volume.
- Storie Instagram (formato 1080×1920) dallo stesso template; upload via Graph API dopo approvazione.
- Bottoni Telegram "approva / scarta / rigenera" che aggiornano `posts.status`.
