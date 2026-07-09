# Mana Vault — Agent Audit Prompts

Copy-paste prompts to send agents in to audit each domain. Scoped to non-overlapping
slices (see `reference/system-map.html`) so you can fan them out in parallel. Every prompt
is **read-only reconnaissance** — investigate and report, change nothing — unless you say so.

Pairs with:
- `reference/system-map.html` — the 7 ownership domains
- `reference/agent-teams-matrix.html` — 3 guilds × 7 domains

---

## 🗄️ pipeline-tester → does the pipeline still run?

> In `~/mana-vault`, verify the data pipeline still works end-to-end **without changing code**.
> Check whether the input files it expects (`AllPrices.json`, `AllPricesToday.json`, the ManaBox
> CSV, `scryfall_to_mtgjson.json`) actually exist on disk. Read `preprocess.py`'s `main()` and
> argparse to confirm the CLI contract (`--csv` / `--output`). If inputs exist, dry-read the first
> ~200 lines of each. Report: what's present, what's missing, and the exact command to regenerate
> `dashboard/public/data/*.json`. Do **not** download anything or run `update.py`.

## 📅 scraper-steward + dashboard-builder → confirm the Events gap

> In `~/mana-vault`, confirm or refute: `scrape_events.py` generates `events.json` but the
> dashboard has **no Events view**. Grep `dashboard/index.html` for `data-view` tabs and `main.js`
> for any events / `renderEvents` handling. Check whether `events.json` is even produced — is
> `scrape_events.py` wired into `update.py`, or run separately? Report the exact gap and the
> smallest change that would wire an Events tab in. Don't make the change yet — just spec it.

## 📊 indicator-verifier → is the TA math correct?

> In `~/mana-vault/preprocess.py`, review `compute_technical_indicators()`. Verify the EMA seed,
> RSI(14) Wilder-vs-simple averaging, and Bollinger(20, 2σ) math against textbook definitions.
> Check the signal-detection loop for off-by-one / lookahead issues (does it use index `i`
> correctly, no future data). Report any bugs with line numbers and the correct formula. Read-only.

## 📈 dashboard-builder → does the frontend load cleanly?

> In `~/mana-vault/dashboard`, audit the SPA. Run `npm install` and `npm run build` (Vite) and
> report any errors. Read `main.js` `loadData()` / `loadPriceHistory()` and confirm every fetched
> JSON (`portfolio`, `cards`, `arbitrage`, `movers`, `price_history`) is actually produced by
> `preprocess.py` `write_output()`. Flag any fetch of a file the pipeline never writes. Report
> build status + any contract mismatches.

## ☁️ release-captain → is the multi-user API deployable?

> In `~/mana-vault`, review `api/main.py`, `api/Dockerfile`, `docker-compose.yml`. Trace the upload
> flow: `POST /api/upload` → `_run_preprocess` shelling out to `preprocess.py --csv/--output`.
> Confirm the CLI flags it passes match what `preprocess.py`'s argparse accepts (known seam). Note
> the CORS `["*"]` and 50MB cap. Report whether `docker compose build` would succeed and any
> pipeline-CLI drift that would break vault creation. Read-only — don't build/run containers unless
> trivially safe.

## 🔍 indicator-verifier → movers & arbitrage sanity

> In `~/mana-vault/preprocess.py`, review `parse_mtgstocks_movers()` and `find_arbitrage()`.
> Confirm: (1) movers join to the collection by card **name** and note the mismatch risk, (2) the
> arbitrage `>15%` threshold and which 3 vendors it compares. Check for divide-by-zero or
> None-price handling. Report bugs + line numbers, read-only.

## 💡 product-strategist → where does this go next?

> You are the **product strategist** for Mana Vault — a Magic: The Gathering collection tracker
> that treats cards like a stock portfolio (price charts, technical indicators, daily movers,
> cross-vendor arbitrage, a multi-vault upload API, and a static "TCG business ideas" microsite).
> Read `README.md`, `AGENTS.md`, `tcg-business/IDEAS.md`, `preprocess.py`, and `dashboard/main.js`
> to ground yourself in what actually exists today.
>
> Your job is **not** to file bugs — it's to see around the corner. Produce a strategist's memo:
>
> 1. **The one-sentence bet.** What is this product actually becoming, and who is the sharpest
>    possible user it should be built for? (Casual collector vs. speculator vs. LGS owner vs.
>    content creator — pick a spearhead, don't hedge.)
> 2. **The obvious next three.** Given what's half-built, what will *I* almost certainly ask for
>    next? Rank by (impact ÷ effort). The Events view is already a known gap — go past it. Think:
>    price alerts / watchlist, deck-value tracking, multi-game (Pokémon/Lorcana/One Piece), a
>    public shareable vault, buylist/sell-timing signals, tax-lot / cost-basis export.
> 3. **What other people need that I haven't thought of.** Adjacent users with money and bad
>    tooling: the LGS owner pricing singles, the grader/flipper, the Commander deck-builder, the
>    Discord community running a "card of the week." For each, one killer feature Mana Vault is
>    uniquely positioned to ship because it already has the price-history + TA engine.
> 4. **The moat.** Everyone can pull MTGJSON prices. What compounds here that a competitor can't
>    copy in a weekend? (Hint: the "cards as an asset class" analytics lens, the arbitrage engine,
>    per-user longitudinal data.) Name the one thing to double down on.
> 5. **The 3 things NOT to build.** Where's the trap — the feature that looks exciting but is a
>    data-quality tar pit or a commodity race to zero?
>
> Be opinionated and specific. Cite the actual files/functions that make each idea cheap or
> expensive to build (e.g. "we already have `compute_technical_indicators`, so X is nearly free").
> End with a single **"if you do one thing this month"** recommendation. Read-only.

## 💡 product-strategist (b) → is the TCG toolkit self-consistent?

> In `~/mana-vault/tcg-business`, review `index.html`, `ideas.html`, `idea-generator.html`, and
> `logging/Code.gs`. Confirm the idea-generator's optional Google-Sheet logging is off-by-default
> and the field list matches `Code.gs` `HEADERS`. Check the Pages workflow
> (`.github/workflows/pages.yml`) actually deploys this folder. Report any broken links or field
> mismatches. Read-only.

---

## Fan-out order (highest signal first)

1. `pipeline-tester` — does it even run? (unblocks everything)
2. `scraper-steward + dashboard-builder` — confirm the Events gap
3. `product-strategist` — where does this go next
4. everything else in parallel
