# 🃏 TCG Business Ideas

A starter brief for a friend kicking around "a TCG business." TCG = **Trading Card Game** —
Magic: The Gathering, Pokémon, Yu-Gi-Oh!, Lorcana, One Piece, Flesh and Blood, sports cards, etc.

It's a deceptively large market: a single-digit-billions secondary market, millions of players,
and a player base that is *online, obsessive, and used to spending money*. Most of the tooling
around it is bad, which is good news for anyone building.

> **Where this list comes from:** the repo this lives in (Mana Vault) already treats an MTG
> collection like a stock portfolio — price charts, technical indicators, daily movers,
> arbitrage detection. That "cards are a financial asset class" lens runs through a lot of the
> ideas below. Steal from it.

---

## How to read this

Each idea has a one-line pitch, who pays, why it's hard, and an honest difficulty/capital read.
Nothing here is novel enough that someone isn't already doing *a* version of it — the edge is
almost always **execution, a specific niche, or better data**, not the idea itself.

Difficulty/capital are rough: 🟢 weekend-to-side-project · 🟡 real commitment · 🔴 needs money or a team.

---

## 1. Software & data (lowest capital, your friend's likely best entry)

These need a laptop and taste, not inventory.

### 1a. Collection-as-portfolio tracker
**Pitch:** "Robinhood for your card binder." Import a collection, value it daily, show P&L,
gainers/losers, allocation by set/rarity.
**Who pays:** serious collectors and speculators; freemium with a paid tier for alerts/history.
**Why it's hard:** clean price data is the whole game (see §4); free competitors exist (this repo
is one). Edge = better UX, multi-game support, or the analytics nobody else does.
**Read:** 🟢 to build a v1 · monetization is the real challenge.

### 1b. Price-alert & "card watchlist" service
**Pitch:** Set alerts — "tell me when [card] crosses $X" or "when any card in my deck spikes >20%."
**Who pays:** speculators, store owners, deck-builders timing buys.
**Why it's hard:** needs reliable, frequent price data + notification plumbing. Low retention if
alerts are noisy.
**Read:** 🟢 great first product; natural upsell on top of 1a.

### 1c. Arbitrage / deal scanner
**Pitch:** Surface cross-vendor price gaps (TCGPlayer vs CardKingdom vs Cardmarket vs eBay sold)
big enough to flip for profit. Mana Vault already does a version of this.
**Who pays:** resellers, "buylist arbitrage" hustlers. Could even take a cut.
**Why it's hard:** vendor terms of service, rate limits, and the fact that obvious gaps close fast.
The money is in *fees, condition, and shipping* nuance that naive scanners miss.
**Read:** 🟡 technically fun, legally/ToS-sensitive.

### 1d. Deck-value & "metagame cost" tools
**Pitch:** Paste a decklist → total cost, cheapest vendor to assemble it, budget swaps, price
trend of the whole deck over time.
**Who pays:** competitive players, content creators, affiliate revenue from "buy this deck" links.
**Why it's hard:** affiliate margins are thin; needs deck-format awareness per game.
**Read:** 🟢 strong affiliate/content angle.

### 1e. Grading-arbitrage / "should I grade this?" calculator
**Pitch:** Given a raw card, estimate expected value after PSA/BGS/CGC grading minus grading cost
and turnaround, across likely grades. Sports-card people obsess over this.
**Who pays:** flippers, submitters; affiliate to grading services.
**Why it's hard:** predicting grade outcomes is genuinely hard (condition from photos).
**Read:** 🟡 — the "from a photo" version is an ML project (see §3).

### 1f. Store/LGS back-office SaaS
**Pitch:** Inventory, buylist pricing, event registration, and POS for local game stores. Most run
on spreadsheets + a patchwork of tools.
**Who pays:** game store owners (B2B — fewer customers but real budgets and stickiness).
**Why it's hard:** B2B sales cycle, support burden, entrenched incumbents (TCGplayer's own tools,
Crystal Commerce). Edge = a wedge feature done dramatically better.
**Read:** 🔴 highest ceiling, slowest start.

---

## 2. Marketplace, retail & physical (higher capital, clearer revenue)

### 2a. Niche reseller / "card flipping" operation
**Pitch:** Buy underpriced, sell at market. Specialize (one game, one era, sealed product, a
specific language/region).
**Who pays:** the market. You *are* the business.
**Why it's hard:** it's a grind, capital-gated, and margins live or die on sourcing + fees.
**Read:** 🟡 capital · the data tools in §1 are how you get an edge here.

### 2b. Sealed-product / "case break" business
**Pitch:** Buy sealed boxes, do live "breaks" (open packs on stream, viewers buy slots/spots).
Huge in sports cards, growing in Pokémon.
**Who pays:** viewers buying into breaks; you take margin + entertainment value.
**Why it's hard:** needs audience-building, streaming chops, trust/escrow, and gambling-adjacent
regulatory questions depending on jurisdiction.
**Read:** 🔴 it's a media business wearing a card-business hat.

### 2c. Subscription box
**Pitch:** Monthly curated cards/singles/accessories for a niche (e.g. "Commander upgrades,"
"vintage Pokémon," "new-player on-ramp").
**Who pays:** subscribers.
**Why it's hard:** sourcing consistency, churn, shipping economics.
**Read:** 🟡.

### 2d. Consignment / authentication / escrow for high-value cards
**Pitch:** Trusted middleman for expensive trades — verify authenticity, hold funds, ship safely.
Counterfeits (esp. high-end MTG/Pokémon) are a real and growing problem.
**Who pays:** buyers/sellers paying for trust; % fee.
**Why it's hard:** trust is everything and slow to build; fraud liability.
**Read:** 🔴.

---

## 3. AI / ML angles (timely, defensible if data is good)

### 3a. Card scanner / instant-ID + condition grading from a photo
**Pitch:** Point your phone at a card → instant identification, set/printing, current value, and a
condition estimate. The condition piece is the unsolved, valuable part.
**Who pays:** collectors cataloging, resellers pricing, integrated into 1a/1f.
**Why it's hard:** real CV/ML work; condition grading from consumer photos is genuinely unsolved at
scale. But "good enough" is a moat.
**Read:** 🟡–🔴.

### 3b. AI deck-builder / coach
**Pitch:** "Build me a budget Commander deck around this commander," or "improve my deck against
the current meta." LLM + card database + metagame data.
**Who pays:** players; affiliate on the resulting shopping list.
**Why it's hard:** correctness (LLMs hallucinate cards/rules), needs current meta data.
**Read:** 🟢 to prototype, 🟡 to make trustworthy.

### 3c. Price-prediction / "card analyst"
**Pitch:** Forecast which cards will rise — reprint risk, tournament results, set rotation, hype.
The literal "treat cards like stocks" thesis, taken to its conclusion.
**Who pays:** speculators (carefully — this is financial-advice-shaped).
**Why it's hard:** prediction is hard; reputational risk if wrong; needs lots of clean history.
**Read:** 🟡 — great *content* even if the model is mediocre.

---

## 4. Content, community & "picks and shovels"

The unsexy truth: in any gold rush, **selling shovels** is the reliable business.

### 4a. Price-data API / aggregator
**Pitch:** Be the clean, reliable data source other builders pay for. Every tool in §1 and §3
needs this and most cobble it together painfully.
**Who pays:** developers, tools, stores (B2B API, usage-based pricing).
**Why it's hard:** data sourcing legality/ToS, freshness, reliability — but if you nail it, you're
infrastructure.
**Read:** 🔴 but the most defensible thing on this list.

### 4b. Newsletter / content brand with affiliate + sponsorship
**Pitch:** "The finance newsletter for card investors." Daily/weekly movers, reprint watch, deals.
Mana Vault's "daily movers" view is literally a newsletter waiting to happen.
**Who pays:** affiliates, sponsors, eventually a paid tier.
**Why it's hard:** audience-building is slow; needs a consistent voice.
**Read:** 🟢 lowest capital of anything here; compounds with every tool above.

### 4c. Tournament / event platform
**Pitch:** Registration, pairings, results, and metagame tracking for local + online events. Mana
Vault already scrapes magic.gg + MTGTop8 for exactly this kind of data.
**Who pays:** organizers, stores, sponsors.
**Why it's hard:** chicken-and-egg adoption; incumbents exist.
**Read:** 🔴.

---

## Honest take for a first-timer

If your friend is a builder with little capital, the smart sequencing is:

1. **Start with content/data (4b + 1a/1b).** A newsletter + a free tracker builds an audience and
   teaches you what people actually want, at near-zero cost.
2. **Turn the audience into a paid tool** (alerts, deck tools, analytics) once you know the pain.
3. **Only then** consider inventory/physical (§2) or infrastructure (§4a), which need money or scale.

The recurring lesson: **the idea is cheap, the data and the audience are the moat.** Mana Vault is
already 60% of a §1 product — the missing 40% is distribution and someone willing to pay.

---

*Next to this file is `idea-generator.html` — open it in a browser. It interviews you (capital,
skills, time, risk appetite, interests) and generates a tailored prompt to paste into Claude/ChatGPT,
plus the idea seeds from this list that best match your answers.*
