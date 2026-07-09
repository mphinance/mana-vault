# SPEC — Mana Vault audit findings build

Implements the top three findings from the agent audit
(`reference/strategist-memo.md`, `reference/pipeline-status.md`).

**Constraints**
- Repo is a fresh clone with **no data**. Verify via `python3 -m py_compile` and `npm run build`
  (Vite), NOT end-to-end runs. All render code must **degrade gracefully on missing/empty JSON**.
- Vanilla JS + Vite dashboard. No new frontend dependencies. Match the existing dark
  glassmorphism theme and the existing patterns (`switchView`, `fmt`, `fmtPct`, `pnlClass`,
  `cardNameLink`, `scryfallImage`, `loadData`).
- Generated JSON lives in `dashboard/public/data/` (gitignored). Snapshot state files gitignored.
- Python: stdlib only (no new deps). Follow existing `preprocess.py` style.

---

## Feature 1 — Price Alerts (the "one thing this month")

New standalone script **`alerts.py`** (does NOT modify `preprocess.py`).

- Reads `dashboard/public/data/price_history.json`. For each card, read `technicals.signals`
  (list of `{date, type, label}`) — the newest signal(s).
- Maintains a snapshot **`dashboard/public/data/alerts_state.json`** (gitignored): last-seen
  signal fingerprint per `scryfall_id` (e.g. `"{type}@{date}"` of the latest signal).
- On each run, emit **`dashboard/public/data/alerts.json`** containing only **NEW** fires since the
  last snapshot, then update the snapshot.
- Optional webhook: `--webhook URL` flag OR `MANA_VAULT_WEBHOOK` env var → POST a compact JSON
  summary (stdlib `urllib.request`). No webhook configured = fully local, no network.
- CLI: `--data DIR` (default `dashboard/public/data`), `--webhook URL`, `--dry-run` (compute but
  don't write snapshot/alerts). First run with no prior snapshot = seed snapshot, emit zero alerts
  (don't spam every historical signal on first run).

### Contract — `alerts.json`
```json
{
  "generated_at": "ISO-8601",
  "count": 3,
  "alerts": [
    {
      "scryfall_id": "…", "name": "…", "set_code": "…", "foil": false,
      "type": "bullish_cross", "label": "EMA 8/21 Bullish Cross", "date": "YYYY-MM-DD",
      "current_price": 12.34, "binder": "…"
    }
  ]
}
```
Sort alerts newest `date` first. `current_price` = latest price from the card's `history` (or
`cards.json` current_price if simpler); null-safe.

---

## Feature 2 — Buylist-vs-Retail Margin

Modify **`preprocess.py`** only. New function **`build_buylist_margins(card_analytics)`**, wired
into `main()` and `write_output()` → emits **`buylist_margins.json`**.

- For each card with both a CardKingdom buylist price and a retail price (reuse the
  `vendor_prices` keys `cardkingdom_buylist_{finish}` and the best of
  `tcgplayer_retail_{finish}` / `cardkingdom_retail_{finish}` / `cardmarket_retail_{finish}`):
  - `margin_abs = best_retail - ck_buylist`
  - `margin_pct = margin_abs / ck_buylist * 100` (guard divide-by-zero / None)
- Skip cards with no buylist or no retail, or ck_buylist <= 0.
- Sort by `margin_pct` desc, cap top 200 (mirror `find_arbitrage`).
- `write_output` gains a `buylist_margins=None` param; writes `buylist_margins.json` when provided,
  same conditional pattern as `movers`/`arbitrage`. `main()` computes it after `find_arbitrage` and
  passes it in (both default and per-user mode).

### Contract — `buylist_margins.json`
```json
[
  {
    "name": "…", "set_code": "…", "foil": false, "scryfall_id": "…", "binder": "…",
    "quantity": 1, "best_retail": 20.0, "retail_vendor": "tcgplayer",
    "ck_buylist": 8.0, "margin_abs": 12.0, "margin_pct": 150.0
  }
]
```

---

## Feature 3 — Events View (close the known gap)

Modify **`dashboard/index.html`**, **`dashboard/main.js`**, **`dashboard/public/style.css`** only.
Render the already-generated `events.json` (nobody consumes it today; only 6 tabs exist).

- Add nav tab `<button class="nav-btn" data-view="events">Events</button>` and a
  `<section id="view-events" class="view">`.
- `loadData()` fetches `events.json` (null-safe: `r.ok ? r.json() : null`).
- `switchView('events')` calls `renderEvents()`:
  - **Upcoming** events (from `events.upcoming`) as cards with type badge + date + link.
  - **Recent tournament results** (`events.recent_events`).
  - **Metagame** snapshot (`events.metagame` = `{format: [archetypes]}`), highlighting
    archetypes with `in_collection: true`.
  - Read `scrape_events.py` `main()` for exact item keys; render defensively (skip missing keys).
- Empty/missing `events.json` → friendly empty state, no console errors.

### Also in Wave 2 (same frontend agent, same files) — surface Alerts + Buylist
- **Alerts tab** (`data-view="alerts"`, `renderAlerts()`) rendering `alerts.json` — list of recent
  fires, each linking to its card's chart (reuse the `switchView('chart')` + `selectCard` pattern).
- **Buylist tab** (`data-view="buylist"`, `renderBuylist()`) rendering `buylist_margins.json` — a
  sortable table (name, retail, buylist, margin $, margin %), framed as "what a store captures."
- Both null-safe on missing JSON.

---

## Out of scope
- Deck-value tracking, multi-game, public-vault gallery, tax export (future).
- No changes to `api/main.py`, `update.py`, `scrape_events.py`, the pipeline's price extraction, or
  `reference/*`.
- No new npm/pip dependencies.

---

# ROUND 2 — growth loop + flipper + digest

Same constraints as above (no data → verify via py_compile + vite build; stdlib only; no new
frontend deps; degrade gracefully). New branch `feat/round2`.

## Feature 4 — Daily Digest (`newsletter.py`, new standalone script)
Reads `dashboard/public/data/{movers,alerts,buylist_margins}.json` (all optional) and emits a
Markdown digest to `dashboard/public/data/digest.md` (and stdout): "Today's Top Movers",
"New Alerts", "Best Buylist Margins". Optional `--webhook URL` / `MANA_VAULT_DIGEST_WEBHOOK`
(stdlib urllib, best-effort). `--dry-run` writes nothing. Missing/empty files → friendly digest,
exit 0. Does NOT modify preprocess.py or alerts.py.

## Feature 5 — Enriched vault list (`api/main.py` only)
Enrich `GET /api/vaults`: for each ready vault, read its `data/portfolio.json` (if present) and
add `total_value` and (if cheap) `top_gainer` to the returned dict. Guard all file reads. Do NOT
touch the frontend. Keep the existing response shape additive (don't remove fields).

## Feature 6 — Public Vault Gallery + Sell Queue (`dashboard/` only, single frontend agent)
- **Gallery**: new `data-view="gallery"` tab + `#view-gallery` section. Fetches `${API_BASE}/vaults`,
  renders ready vaults as clickable cards (name, card_count, total_value if present) that open
  `?vault=slug`. Empty/failed fetch → friendly empty state. Reuse `fmt`.
- **Sell Queue**: within the existing Signals view (or a sub-panel), surface OWNED cards whose
  latest signal is bearish (`bearish_cross`/`overbought`/`bb_upper_break`), ranked by
  `pnl × quantity` (dollar impact). Reuse `cards.json` (already loaded) joined to signals from the
  signals data already in memory. Framed as "Sell Queue" with dollar impact shown. Degrade
  gracefully when no holdings/signals.
