# STATUS — Audit-findings build

Branch: `feat/audit-findings` · **18/18 features passing** · all commits verified.

Shipped the top three findings from the agent audit (`reference/strategist-memo.md`).

## What shipped

### 1. Price Alerts — `alerts.py` (new, standalone)
The "one thing this month." Reads `technicals.signals` already emitted per card in
`price_history.json`, diffs against a snapshot (`alerts_state.json`), and writes **only new fires**
to `alerts.json`.
- First run seeds the snapshot and emits **zero** alerts (no historical spam).
- Optional webhook via `--webhook URL` or `MANA_VAULT_WEBHOOK` (stdlib only; no config = no network).
- `--dry-run` computes without writing. Missing data → exits cleanly, no traceback.
- Does not touch `preprocess.py`. stdlib only.

### 2. Buylist-vs-Retail Margin — `preprocess.py`
Surfaces the CardKingdom buylist price that was already captured but unused (the LGS wedge).
New `build_buylist_margins()` → `buylist_margins.json`: best retail vs `ck_buylist`, margin $ and %,
divide-by-zero guarded, sorted desc, top 200. Runs in **both** default and per-user mode.

### 3. Events view + Alerts/Buylist tabs — `dashboard/`
Closed the known gap: `events.json` was generated but never rendered (only 6 tabs existed).
Added three tabs — **Events** (upcoming + recent results + metagame, `in_collection` highlighted),
**Alerts** (fires link to the card chart), **Buylist** (sortable margin table). All null-safe with
friendly empty states. Reuses existing helpers (`fmt`/`fmtPct`/`switchView`/`selectCard`). Zero new deps.

## Verification
- `python3 -m py_compile alerts.py preprocess.py` → clean.
- `alerts.py --dry-run` with no data → graceful exit 0.
- `cd dashboard && npm run build` → `✓ built in ~2.4s`, exit 0.
- `dashboard/package.json` unchanged (no new dependencies).

## Commits (wave-by-wave)
- `31713da` Wave 0: scaffold (SPEC + feature_list + reference maps)
- `cd48ec7` buylist margins
- `0d09ba8` alerts engine
- `86fd845` verify wave 1 (10/18)
- `a6061e6` dashboard views
- (final) verify wave 2 + STATUS

## Not tested (no data in this clone)
All verification was compile + build only — the repo has no `AllPrices.json` / collection CSV.
End-to-end behavior (real signal fires, real margins, populated views) is unverified until the
pipeline is hydrated: supply `ManaBox_Collection.csv` + `scryfall_to_mtgjson.json`, then
`python3 update.py --full && python3 alerts.py`. See `reference/pipeline-status.md`.

## Follow-ups (deferred, from the memo)
- Wire `alerts.py` into `update.py` (or a cron) so alerts fire automatically after each daily refresh.
- Public shareable-vault gallery (`GET /api/vaults` exists, unused) — the growth loop.
- Deck-value tracking (needs pricing cards outside the owned set — real pipeline change).

---

## Round 2 — growth loop + flipper (branch feat/round2 → merged)

- **`newsletter.py`** (new) — daily Markdown digest from movers + alerts + buylist → `digest.md` + optional webhook (`MANA_VAULT_DIGEST_WEBHOOK`). stdlib only, `--dry-run`, degrades on no data.
- **`GET /api/vaults`** — additively enriched with optional per-vault `total_value` (from `total_current`), fully guarded.
- **Public Vault Gallery** — new `gallery` tab; lists ready vaults as clickable cards → `?vault=slug`. The growth loop (every shared vault is an ad).
- **Sell Queue** — inside Signals: owned cards flashing bearish signals (`bearish_cross`/`overbought`/`bb_upper_break`) ranked by `pnl × quantity`. Reuses the lazy-loaded price history; no extra fetch.

Verification: py_compile clean, `newsletter.py --dry-run` exit 0, `npm run build` exit 0, zero new deps. 24/24 features passing.

---

## Round 3 — digest API + buy queue (branch feat/round3 → merged)

- **`newsletter.py`** refactored — exposed pure `build_digest(data_dir) -> dict` (`generated_at`/`markdown`/`movers`/`alerts`/`buylist`), importable with no side effects; old markdown builder split out as `build_markdown()`. CLI unchanged.
- **`GET /api/digest`** — serves the digest as JSON (optional `?vault=slug`, else shared dashboard data). Guarded: missing dir or any error → 200 with empty-but-valid sections, never a 500.
- **Buy Queue** — inside Signals: owned cards flashing the latest bullish signal (`bullish_cross`/`oversold`/`bb_lower_break`) ranked by `current_price × quantity`. Reuses the lazy-loaded price history; row click → chart. The inverse of the Sell Queue.

Verification: py_compile clean, `build_digest('/tmp/nope')` returns valid empty dict, `npm run build` exit 0 (~2.1s), zero new deps. 29/29 features passing.
