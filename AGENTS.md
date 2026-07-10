# AGENTS.md

## Project: Mana Vault

MTG collection tracker that treats cards like stocks. Vanilla JS + Vite dashboard with a Python data pipeline.

## Architecture

```
ManaBox CSV + Sealed_Products.csv + AllPrices.json (MTGJSON, 1.2GB)
        │
    preprocess.py  ──→  dashboard/public/data/*.json
        │
    dashboard/main.js  ──→  Single-page app (Lightweight Charts)
```

Sealed product (boxes, bundles, Secret Lairs) is loaded from `Sealed_Products.csv`
(root, gitignored) and folded into the same portfolio: `portfolio.json` gains
`sealed_*` + `grand_total_*` fields, and `sealed.json` holds per-item detail. The
Portfolio total and header roll singles + sealed into one combined number.

### Python Scripts (project root)
- **`preprocess.py`** — Core data pipeline. Single-pass streaming extraction from AllPrices.json. Computes EMA, SMA, RSI, Bollinger Bands. Outputs portfolio.json, cards.json, price_history.json (~140MB), movers.json, arbitrage.json.
- **`update.py`** — Downloads fresh MTGJSON data, re-runs preprocessor. `--full` flag for 90-day history.
- **`scrape_events.py`** — Playwright scraper for magic.gg schedule + MTGTop8 tournament results/metagame.

### Dashboard (`dashboard/`)
- **`main.js`** — All rendering logic. ~1200 lines. Views: Portfolio, Price Charts, Movers, Signals, Arbitrage, Collection, Sealed, Events, Alerts, Buylist, Gallery.
- **`index.html`** — Single HTML file with all 7 view sections.
- **`public/style.css`** — Dark theme with CSS custom properties. Glassmorphism + monospace prices.

## Key Patterns

**Navigation**: `switchView(view, { pushHistory })` — Tab-based. Cross-view navigation pushes history for back-button support.

**Charts**: Lightweight Charts (TradingView). `priceChart.addSeries(LineSeries, {...})`. Price line is white 3px, indicators are thinner colored lines.

**Link Helpers**: `cardNameLink(name, set, num)` → Scryfall, `priceLink(price, name, vendor)` → TCGPlayer/CK, `mtgstocksLink(name)` → MTGStocks.

**Formatting**: `fmt(n)` → `$1,234.56`, `fmtPct(n)` → `+12.34%`, `pnlClass(n)` → `'positive'`/`'negative'`.

**Data Loading**: `loadData()` fetches all small JSONs upfront. `loadPriceHistory()` lazy-loads the 140MB file only when Price Charts view is opened.

## Card Identity
- **Scryfall ID** — Primary key in frontend (image URLs, linking)
- **MTGJSON UUID** — Used for price data lookups in preprocess.py
- **`scryfall_to_mtgjson.json`** — Maps between the two (gitignored)

## Data Files (all gitignored, generated)
| File | Size | Contents |
|------|------|----------|
| `portfolio.json` | ~11KB | Summary stats, daily portfolio values, breakdowns |
| `cards.json` | ~4.5MB | Per-card summary (no history) |
| `price_history.json` | ~140MB | Per-card price history + technicals |
| `movers.json` | ~56KB | MTGStocks daily movers |
| `arbitrage.json` | ~58KB | Cross-vendor price gaps >15% |
| `sealed.json` | ~1KB | Per-item sealed product analytics |
| `events.json` | ~16KB | Tournament schedule + metagame |
