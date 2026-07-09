# Strategist's Memo — Mana Vault

> Product-strategy read of the Mana Vault codebase (an MTG collection tracker that treats
> cards like a stock portfolio). Read-only research — no files were changed. Every claim is
> tied to a real file/function so you can see what's cheap vs. expensive to build.
>
> Pairs with `reference/system-map.html` and `reference/agent-teams-matrix.html`.

---

## The reframe (read this first)

The technical-analysis engine you built — `compute_technical_indicators` (EMA/SMA/RSI/Bollinger
+ crossover/breakout signal detection), `find_arbitrage`, the movers cross-reference — is aimed
at a single owner's collection. But the one genuinely differentiated piece of infrastructure is
the **multi-vault upload pipeline in `api/main.py`**, and the accumulating **per-user price
history** it produces.

**The TA is table-stakes. The per-vault pipeline + retained history is the asset.** That reframe
drives everything below.

---

## 1. The one-sentence bet

**Mana Vault is becoming "Bloomberg Terminal for MTG speculators" — and the sharpest user to
build for is the speculator/flipper who already thinks of cards as a tradeable asset class, not
the casual collector who just wants a shelf inventory.**

Why the speculator, not the others: every non-trivial thing already in the code serves *them*.
`compute_technical_indicators`, `find_arbitrage` (with `ck_buylist` already captured), and
`parse_mtgstocks_movers` cross-referenced against holdings mean nothing to a casual collector
(who wants a scanner and a total) and everything to someone timing buys and sells. The casual
collector is a bigger *market* but a worse *spearhead* — you'd have to rip out your best work to
serve them. **Build for the person your engine already flatters.**

---

## 2. The obvious next three (ranked by impact ÷ effort)

### #1 — Price alerts / watchlist  ·  highest ratio, nearly free
Signal detection already runs on every card in `compute_technical_indicators` (lines ~395–423):
bullish cross, RSI oversold, BB breakout — all date-stamped. `update.py` already re-runs the
pipeline daily. An alert is just: **diff today's `signals[]` array against yesterday's, fire on
new entries.** You are one daily cron + one delivery channel (Discord/email webhook) away from
the alert product `IDEAS.md §1b` calls the "great first product." The engine computes the trigger
already; you're only missing the notification pipe. **Effort: days.**

### #2 — Public shareable vault  ·  plumbing exists, polish doesn't
`api/main.py` already writes per-vault data to `user_data/{slug}/data/`, and `main.js`'s
`getDataBase()` / `detectVault()` / `showVaultBar()` already render any vault by `?vault=slug`.
The Copy-Link button is *already wired* (`initVaultBar`, ~line 1004). Missing: a read-only public
gallery (`GET /api/vaults` exists but nothing consumes it) and an OG/share-card so a vault link
looks good pasted in Discord. **This is the cheapest growth loop you have — every shared vault is
an ad.** Effort: low-to-medium, mostly frontend.

### #3 — Deck-value tracking  ·  real value, real effort
Your TA engine could chart a whole deck's value over time exactly like `renderPortfolioChart`
charts `portfolio.portfolio_values`. But there's a genuine cost: today card identity is keyed on
`mtgjson_uuid` via `scryfall_to_mtgjson.json` *for cards you own*. A decklist is arbitrary
printings you may not hold, so `extract_prices_fast` can no longer scope to `needed_uuids` from
the CSV. That's a real pipeline change, not a bolt-on. Worth doing — but it's the effortful one.

> **Deprioritize:** tax-lot / cost-basis export looks cheap (`purchase_price` / `total_purchase`
> already tracked per card) but serves accountants, not your spearhead speculator. Later, not next.

---

## 3. What other people need (adjacent users, money, bad tooling)

**The LGS owner pricing singles — "Buylist Sanity Check."**
You already capture `cardkingdom_buylist` in `extract_prices_fast` (line ~168, the `buylist`
price_type) and `find_arbitrage` (`ck_buylist`, line ~628) — but you *only surface retail
spreads*. An LGS owner buying cards off customers needs the inverse: "what will CK/TCGPlayer pay
me, and what's my margin if I buy at X?" **The buylist data is already parsed and thrown away.**
Ship a buylist-vs-retail margin view and you've built the store-market wedge (`IDEAS.md §1f`)
from data you already have.

**The flipper — "Should I hold?" sell-timing.**
Your engine detects `overbought` (RSI >70) and `bb_upper_break` per card. The flipper's killer
feature is a ranked **"sell now" queue**: my holdings flashing distribution signals, sized by
`pnl × quantity`. `renderSignals` (main.js ~732) already splits bullish/bearish — it's 80% there;
it just isn't framed as a sell queue with dollar impact attached.

**The Commander deck-builder — "reprint-risk radar."**
Needs the deck-pricing work from §2 #3, but the payoff is unique: chart an EDH deck's aggregate
value and flag cards whose RSI/BB pattern suggests a spike (buy the dip before you build).
**Nobody prices a whole EDH deck as a portfolio with technicals.** You'd be first.

**The Discord community running "card of the week" — the movers feed is a newsletter.**
`parse_mtgstocks_movers` already produces a dated, collection-flagged movers list (`IDEAS.md §4b`
says this literally is a newsletter waiting to happen). One endpoint emitting "today's top 10
movers + which flashed signals" as formatted text is a near-zero-marginal-cost content product —
and it feeds the sharing loop from §2 #2.

---

## 4. The moat

**Double down on per-vault price *history* — the accumulating, dated time series, not the
indicators computed from it.**

Anyone can pull MTGJSON's `AllPrices.json` and recompute EMA/RSI in a weekend; the formulas in
`compute_technical_indicators` are commodity. What a competitor *cannot* clone in a weekend is a
growing, per-user, dated record of prices tied to what real people actually own and paid
(`purchase_price`, `total_purchase`, foil/finish, condition). Every day `update.py` runs, every
vault's `price_history.json` gets one row longer. MTGJSON gives a rolling ~90-day window; a
competitor starting today starts from zero and **cannot back-fill.** Snapshot daily, never let
the window reset, treat the history archive as the crown jewel. **It compounds literally by the
day.**

---

## 5. The 3 things NOT to build

1. **Photo-based condition grading / card scanner** (`IDEAS.md §3a`). Exciting, but a from-scratch
   CV/ML project with zero leverage from your stack — everything assumes a clean ManaBox CSV
   (`load_collection`). Different company. Tar pit.

2. **A generic price-data API to sell to other devs** (`IDEAS.md §4a`). Reselling MTGJSON with
   extra steps — commodity race to zero, ToS-exposed, and it competes with your own data source.
   Your edge is the *collection-anchored* layer on top, not the raw feed.

3. **Broad multi-game expansion (Pokémon/Lorcana/One Piece) — yet.** Tempting for TAM, but every
   game needs its own price source, identity map, and foil taxonomy. Your pipeline is welded to
   MTGJSON UUIDs + ManaBox schema; each new game re-plumbs `extract_prices_fast` and
   `scryfall_to_mtgjson.json` and dilutes the one-game history moat. Go multi-game *after* you've
   won MTG speculators, not to chase them.

---

## If you do one thing this month

> **Ship price alerts (§2 #1).** Your signal engine already computes every trigger daily in
> `compute_technical_indicators`; you are one cron-diff and one Discord/email webhook away from
> turning a dashboard nobody remembers to open into a service that pings your sharpest user
> exactly when their money is on the line — and it's the natural paid upsell on top of everything
> already built.
