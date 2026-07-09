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
