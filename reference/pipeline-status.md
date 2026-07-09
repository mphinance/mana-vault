# Pipeline Status — Mana Vault

> Read-only reconnaissance of whether the data pipeline can run right now. Nothing was
> downloaded, run, or modified. Snapshot as of a fresh checkout.

## TL;DR

**The repo is a fresh clone with zero data — nothing is broken, it's just unhydrated.** To see
it run you must supply your own ManaBox export + the Scryfall↔MTGJSON identity map, then
download MTGJSON prices.

---

## 1. Inputs — 0 / 5 present

| File | Expected location | Status | Notes |
|---|---|---|---|
| `AllPrices.json` | repo root | ❌ missing | MTGJSON 90-day history, ~1.2GB. Downloadable via `update.py --full`. |
| `AllPricesToday.json` | repo root | ❌ missing | Today's prices, ~50MB. Downloadable via `update.py`. |
| `ManaBox_Collection.csv` | repo root | ❌ missing | **Your collection — not downloadable.** Only `dashboard/public/manabox_template.csv` (787B) exists as an example. |
| `scryfall_to_mtgjson.json` | repo root | ❌ missing | **Card-identity bridge — not downloadable**, gitignored. Must be generated/supplied. |
| `chat.txt` | repo root | ❌ missing | Pasted MTGStocks movers data. Only read in default mode (skipped when `--csv` is passed). |

## 2. CLI contract (`preprocess.py`)

```
python3 preprocess.py [--csv PATH] [--output DIR]
  --csv     default: ManaBox_Collection.csv (repo root)
  --output  default: dashboard/public/data/
```

**Load chain:** `load_collection(csv)` → `extract_prices_fast(cards)` (single streaming pass over
`AllPrices.json`, scoped to `needed_uuids`) → `build_portfolio_analytics()` →
`parse_mtgstocks_movers()` *(default mode only — reads `chat.txt`)* → `find_arbitrage()` →
`write_output()`.

Per-vault mode (`--csv` set) **skips movers** — movers are global, not user-scoped. This is the
path `api/main.py` uses for uploads.

## 3. Outputs — 0 / 5 present

`dashboard/public/data/` **does not exist yet** (created automatically by `write_output()` via
`os.makedirs(..., exist_ok=True)`). Expected files once generated:

| File | Contents |
|---|---|
| `portfolio.json` | P&L, total value, daily portfolio values, binder/rarity summaries |
| `cards.json` | Per-card summary (no history) — powers the collection table |
| `price_history.json` | Per-card histories + technical indicators (~140MB, lazy-loaded) |
| `movers.json` | MTGStocks daily movers matching the collection (default mode only) |
| `arbitrage.json` | Cross-vendor gaps >15%, top ~200 |

## 4. Regenerate command

```bash
cd ~/mana-vault
python3 update.py --full     # downloads MTGJSON (full 90-day) then auto-runs preprocess.py
# or:
python3 update.py            # today's prices only, then auto-runs preprocess.py
```

`update.py` backs up any existing price file before overwrite and restores it on failure.

## 5. Can it run now? — ❌ blocked

Default mode needs 4 files that aren't present. **Two of them are not downloadable** and are on
you to supply: `ManaBox_Collection.csv` (your collection) and `scryfall_to_mtgjson.json` (the
identity map). `update.py --full` fetches the two MTGJSON price files but **not** those two.

**Bootstrap path:**
1. Drop your `ManaBox_Collection.csv` in the repo root.
2. Supply/generate `scryfall_to_mtgjson.json`.
3. (Optional, for movers) paste MTGStocks data into `chat.txt`.
4. `python3 update.py --full` — downloads prices and runs the preprocessor.
5. `cd dashboard && npm install && npm run dev`.
