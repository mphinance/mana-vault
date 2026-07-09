#!/usr/bin/env python3
"""
Mana Vault — Data Preprocessor
Fast single-pass extraction of collection price history from MTGJSON data.

Usage:
  python3 preprocess.py                                    # default (owner collection)
  python3 preprocess.py --csv path/to.csv --output path/   # per-user mode (skips movers)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DATA_DIR, "dashboard", "public", "data")


def load_collection(csv_path=None):
    """Load ManaBox collection CSV and UUID mapping."""
    print("📦 Loading collection...")
    
    with open(os.path.join(DATA_DIR, "scryfall_to_mtgjson.json")) as f:
        scry_to_mtg = json.load(f)
    
    csv_file = csv_path or os.path.join(DATA_DIR, "ManaBox_Collection.csv")
    with open(csv_file) as f:
        rows = list(csv.DictReader(f))
    
    cards = []
    for row in rows:
        scry_id = row["Scryfall ID"]
        mtg_uuid = scry_to_mtg.get(scry_id)
        if not mtg_uuid:
            continue
        
        purchase_price = float(row["Purchase price"]) if row["Purchase price"] else 0
        qty = int(row["Quantity"]) if row["Quantity"] else 1
        foil_val = row["Foil"].strip().lower()
        finish = "foil" if foil_val in ("foil", "etched") else "normal"
        
        cards.append({
            "name": row["Name"],
            "set_code": row["Set code"],
            "set_name": row["Set name"],
            "collector_number": row["Collector number"],
            "foil": row["Foil"],
            "rarity": row["Rarity"],
            "quantity": qty,
            "scryfall_id": scry_id,
            "mtgjson_uuid": mtg_uuid,
            "purchase_price": purchase_price,
            "total_purchase": purchase_price * qty,
            "condition": row["Condition"],
            "language": row["Language"],
            "binder": row["Binder Name"],
            "binder_type": row["Binder Type"],
            "finish": finish,
        })
    
    print(f"  Loaded {len(cards)} card entries across {len(set(c['binder'] for c in cards))} binders")
    return cards


def extract_prices_fast(cards):
    """
    Single-pass extraction: build a set of needed UUIDs, then stream through
    AllPrices.json looking for UUID keys that match. Much faster than per-UUID search.
    """
    print("💰 Extracting price history from AllPrices.json (1.2GB)...")
    
    needed_uuids = set(c["mtgjson_uuid"] for c in cards)
    print(f"  Looking for {len(needed_uuids)} unique UUIDs...")
    
    prices = {}
    prices_path = os.path.join(DATA_DIR, "AllPrices.json")
    file_size = os.path.getsize(prices_path)
    start_time = time.time()
    
    # Build a fast lookup set for prefix matching
    # MTGJSON UUIDs are like: "0d3dfdf9-27b9-5077-b13a-5ea3ebea2d91"
    uuid_set = needed_uuids.copy()
    
    with open(prices_path, "r") as f:
        bytes_read = 0
        # Skip the meta section
        buffer = ""
        in_data = False
        current_uuid = None
        brace_depth = 0
        current_entry = ""
        
        while True:
            chunk = f.read(4_000_000)  # 4MB chunks
            if not chunk:
                break
            bytes_read += len(chunk)
            buffer += chunk
            
            # Process buffer
            while buffer:
                if not in_data:
                    # Look for "data":{
                    data_idx = buffer.find('"data":{')
                    if data_idx >= 0:
                        buffer = buffer[data_idx + 8:]
                        in_data = True
                    else:
                        buffer = buffer[-20:]  # Keep tail in case "data":{ spans chunks
                        break
                
                if current_uuid is None:
                    # Looking for next UUID key: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx":
                    uuid_match = re.search(r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})":', buffer)
                    if uuid_match:
                        uuid_candidate = uuid_match.group(1)
                        buffer = buffer[uuid_match.end():]
                        
                        if uuid_candidate in uuid_set:
                            current_uuid = uuid_candidate
                            brace_depth = 0
                            current_entry = ""
                        else:
                            # Skip this entry - find the end of its value
                            # Need to track braces to skip the full object
                            skip_depth = 0
                            skip_pos = 0
                            found_end = False
                            for i, ch in enumerate(buffer):
                                if ch == '{':
                                    skip_depth += 1
                                elif ch == '}':
                                    skip_depth -= 1
                                    if skip_depth == 0:
                                        buffer = buffer[i + 1:]
                                        found_end = True
                                        break
                            if not found_end:
                                # Need more data - put UUID marker back isn't needed, 
                                # just break and read more
                                break
                    else:
                        # No UUID found yet, but keep tail for partial matches
                        if len(buffer) > 200:
                            buffer = buffer[-100:]
                        break
                else:
                    # We're collecting an entry for a UUID we care about
                    for i, ch in enumerate(buffer):
                        current_entry += ch
                        if ch == '{':
                            brace_depth += 1
                        elif ch == '}':
                            brace_depth -= 1
                            if brace_depth == 0:
                                # Got complete entry!
                                try:
                                    entry = json.loads(current_entry)
                                    paper = entry.get("paper", {})
                                    card_prices = {}
                                    
                                    for vendor in ["tcgplayer", "cardkingdom", "cardmarket", "manapool"]:
                                        vendor_data = paper.get(vendor, {})
                                        currency = vendor_data.get("currency", "USD")
                                        
                                        for price_type in ["retail", "buylist"]:
                                            type_data = vendor_data.get(price_type, {})
                                            for finish_type in ["normal", "foil"]:
                                                date_prices = type_data.get(finish_type, {})
                                                if date_prices and isinstance(date_prices, dict):
                                                    key = f"{vendor}_{price_type}_{finish_type}"
                                                    card_prices[key] = date_prices
                                    
                                    if card_prices:
                                        prices[current_uuid] = card_prices
                                        uuid_set.discard(current_uuid)
                                except json.JSONDecodeError:
                                    pass
                                
                                buffer = buffer[i + 1:]
                                current_uuid = None
                                current_entry = ""
                                break
                    else:
                        # Consumed entire buffer, need more data
                        buffer = ""
                        break
            
            # Progress
            pct = bytes_read / file_size * 100
            if bytes_read % 40_000_000 < 4_000_000:
                elapsed = time.time() - start_time
                print(f"  {pct:.0f}% — {len(prices)} found, {len(uuid_set)} remaining ({elapsed:.0f}s)")
            
            if not uuid_set:
                break
    
    elapsed = time.time() - start_time
    print(f"  ✅ Done in {elapsed:.0f}s — found prices for {len(prices)}/{len(needed_uuids)} UUIDs")
    
    return prices


def parse_mtgstocks_movers(cards):
    """Parse the MTGStocks daily movers from chat.txt."""
    print("📊 Parsing MTGStocks daily movers from chat.txt...")
    
    chat_path = os.path.join(DATA_DIR, "chat.txt")
    with open(chat_path) as f:
        content = f.read()
    
    # Build collection name lookup
    collection_names = defaultdict(list)
    for card in cards:
        name_lower = card["name"].lower().strip()
        # Also store first word for partial matching
        collection_names[name_lower].append(card)
    
    movers = []
    current_date = None
    current_section = None
    
    for line in content.split("\n"):
        line = line.strip()
        
        date_match = re.search(r"Interests of (\w+ \d+, \d{4})", line)
        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
            continue
        
        if "Average price" in line:
            current_section = "average"
            continue
        elif "Market price" in line:
            current_section = "market"
            continue
        elif "Powered by" in line:
            current_section = None
            continue
        
        mover_match = re.match(
            r"(.+?)\s+\(([^)]+)\)\s+\$([0-9,.]+)\s+\(([▲▼])([0-9.]+)%\)",
            line
        )
        if mover_match and current_date:
            name = mover_match.group(1).strip()
            set_code = mover_match.group(2).strip()
            price = float(mover_match.group(3).replace(",", ""))
            direction = "up" if mover_match.group(4) == "▲" else "down"
            pct_change = float(mover_match.group(5))
            if direction == "down":
                pct_change = -pct_change
            
            name_lower = name.lower().strip()
            # Try both exact and partial name matching (strip set variants)
            in_collection = name_lower in collection_names
            collection_matches = []
            if not in_collection:
                # Try base name (before comma for double-faced/split cards)
                base_name = name_lower.split(",")[0].strip()
                for cname in collection_names:
                    if base_name in cname or cname.startswith(base_name):
                        in_collection = True
                        collection_matches.extend([
                            {"binder": c["binder"], "purchase_price": c["purchase_price"], 
                             "quantity": c["quantity"], "name": c["name"]}
                            for c in collection_names[cname]
                        ])
            else:
                collection_matches = [
                    {"binder": c["binder"], "purchase_price": c["purchase_price"], 
                     "quantity": c["quantity"], "name": c["name"]}
                    for c in collection_names[name_lower]
                ]
            
            movers.append({
                "date": current_date,
                "name": name,
                "set_code": set_code,
                "price": price,
                "pct_change": pct_change,
                "direction": direction,
                "price_type": current_section or "unknown",
                "in_collection": in_collection,
                "collection_matches": collection_matches[:5],  # Cap matches
            })
    
    in_coll_count = sum(1 for m in movers if m["in_collection"])
    unique_dates = len(set(m["date"] for m in movers))
    print(f"  Parsed {len(movers)} mover entries across {unique_dates} days")
    print(f"  🔥 {in_coll_count} movers match cards in the collection!")
    
    return movers


def compute_technical_indicators(history):
    """Compute EMA, SMA, RSI, and Bollinger Bands for a price series."""
    if len(history) < 3:
        return {}
    
    prices = [h["price"] for h in history]
    dates = [h["date"] for h in history]
    
    def sma(data, period):
        result = [None] * len(data)
        for i in range(period - 1, len(data)):
            result[i] = round(sum(data[i - period + 1:i + 1]) / period, 4)
        return result
    
    def ema(data, period):
        result = [None] * len(data)
        if len(data) < period:
            return result
        # Start with SMA for first value
        result[period - 1] = sum(data[:period]) / period
        multiplier = 2 / (period + 1)
        for i in range(period, len(data)):
            result[i] = round((data[i] - result[i - 1]) * multiplier + result[i - 1], 4)
        return result
    
    def rsi(data, period=14):
        result = [None] * len(data)
        if len(data) < period + 1:
            return result
        
        gains = []
        losses = []
        for i in range(1, len(data)):
            change = data[i] - data[i - 1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            if i == period:
                if avg_loss == 0:
                    result[i + 1] = 100
                else:
                    rs = avg_gain / avg_loss
                    result[i + 1] = round(100 - (100 / (1 + rs)), 2)
            else:
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                if avg_loss == 0:
                    result[i + 1] = 100
                else:
                    rs = avg_gain / avg_loss
                    result[i + 1] = round(100 - (100 / (1 + rs)), 2)
        
        return result
    
    def bollinger(data, period=20, num_std=2):
        upper = [None] * len(data)
        lower = [None] * len(data)
        middle = sma(data, period)
        
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            mean = middle[i]
            std = (sum((x - mean) ** 2 for x in window) / period) ** 0.5
            upper[i] = round(mean + num_std * std, 4)
            lower[i] = round(mean - num_std * std, 4)
        
        return middle, upper, lower
    
    indicators = {}
    
    # Moving averages
    indicators["sma_7"] = sma(prices, 7)
    indicators["sma_21"] = sma(prices, 21)
    indicators["sma_50"] = sma(prices, 50)
    indicators["ema_8"] = ema(prices, 8)
    indicators["ema_21"] = ema(prices, 21)
    
    # RSI
    indicators["rsi_14"] = rsi(prices, 14)
    
    # Bollinger Bands
    bb_mid, bb_upper, bb_lower = bollinger(prices, 20, 2)
    indicators["bb_upper"] = bb_upper
    indicators["bb_lower"] = bb_lower
    indicators["bb_mid"] = bb_mid
    
    # Signal detection
    signals = []
    ema8 = indicators["ema_8"]
    ema21 = indicators["ema_21"]
    rsi_vals = indicators["rsi_14"]
    
    for i in range(1, len(prices)):
        # EMA crossover signals
        if ema8[i] is not None and ema8[i-1] is not None and ema21[i] is not None and ema21[i-1] is not None:
            if ema8[i-1] <= ema21[i-1] and ema8[i] > ema21[i]:
                signals.append({"date": dates[i], "type": "bullish_cross", "label": "EMA 8/21 Bullish Cross"})
            elif ema8[i-1] >= ema21[i-1] and ema8[i] < ema21[i]:
                signals.append({"date": dates[i], "type": "bearish_cross", "label": "EMA 8/21 Bearish Cross"})
        
        # RSI signals
        if rsi_vals[i] is not None:
            if rsi_vals[i] > 70:
                signals.append({"date": dates[i], "type": "overbought", "label": f"RSI Overbought ({rsi_vals[i]})"})
            elif rsi_vals[i] < 30:
                signals.append({"date": dates[i], "type": "oversold", "label": f"RSI Oversold ({rsi_vals[i]})"})
        
        # Bollinger Band breakout
        if bb_upper[i] is not None:
            if prices[i] > bb_upper[i]:
                signals.append({"date": dates[i], "type": "bb_upper_break", "label": "Above Upper Bollinger"})
            elif prices[i] < bb_lower[i]:
                signals.append({"date": dates[i], "type": "bb_lower_break", "label": "Below Lower Bollinger"})
    
    indicators["signals"] = signals
    
    # Package as date-indexed for frontend
    result = {"dates": dates}
    for key in ["sma_7", "sma_21", "sma_50", "ema_8", "ema_21", "rsi_14", "bb_upper", "bb_lower", "bb_mid"]:
        result[key] = indicators[key]
    result["signals"] = signals
    
    return result


def build_portfolio_analytics(cards, prices):
    """Calculate portfolio-level analytics with technical indicators."""
    print("📈 Building portfolio analytics...")
    
    all_dates = set()
    for uuid, vendor_prices in prices.items():
        for key, date_prices in vendor_prices.items():
            all_dates.update(date_prices.keys())
    
    all_dates = sorted(all_dates)
    if not all_dates:
        print("  ⚠️  No dates found in price data!")
        return {}, []
    
    print(f"  Date range: {all_dates[0]} → {all_dates[-1]} ({len(all_dates)} days)")
    
    # Calculate portfolio value over time
    portfolio_values = {}
    for date in all_dates:
        total_value = 0
        cards_priced = 0
        for card in cards:
            uuid = card["mtgjson_uuid"]
            if uuid not in prices:
                continue
            price_key = f"tcgplayer_retail_{card['finish']}"
            if price_key not in prices[uuid]:
                price_key = f"cardkingdom_retail_{card['finish']}"
            if price_key not in prices[uuid]:
                alt = "foil" if card["finish"] == "normal" else "normal"
                price_key = f"tcgplayer_retail_{alt}"
            if price_key not in prices[uuid]:
                continue
            if date in prices[uuid][price_key]:
                total_value += prices[uuid][price_key][date] * card["quantity"]
                cards_priced += 1
        portfolio_values[date] = round(total_value, 2)
    
    total_purchase = sum(c["total_purchase"] for c in cards)
    
    # Per-card analytics
    card_analytics = []
    latest_date = all_dates[-1]
    
    for card in cards:
        uuid = card["mtgjson_uuid"]
        current_price = None
        price_history = []
        vendor_prices_current = {}
        
        if uuid in prices:
            # Find best price key for this card
            finish = card["finish"]
            for try_key in [f"tcgplayer_retail_{finish}", f"cardkingdom_retail_{finish}",
                           f"tcgplayer_retail_{'foil' if finish == 'normal' else 'normal'}",
                           f"cardkingdom_retail_{'foil' if finish == 'normal' else 'normal'}"]:
                if try_key in prices[uuid]:
                    price_key = try_key
                    break
            else:
                price_key = None
            
            if price_key:
                dp = prices[uuid][price_key]
                for d in sorted(dp.keys()):
                    price_history.append({"date": d, "price": dp[d]})
                if latest_date in dp:
                    current_price = dp[latest_date]
                elif dp:
                    current_price = dp[max(dp.keys())]
            
            # All vendor prices at latest date
            for key, dp in prices[uuid].items():
                if latest_date in dp:
                    vendor_prices_current[key] = dp[latest_date]
                elif dp:
                    vendor_prices_current[key] = dp[max(dp.keys())]
        
        # P&L
        if current_price and card["purchase_price"] > 0:
            pnl = (current_price - card["purchase_price"]) * card["quantity"]
            pnl_pct = ((current_price / card["purchase_price"]) - 1) * 100
        else:
            pnl = 0
            pnl_pct = 0
        
        # Period changes
        change_7d = change_30d = change_90d = None
        if len(price_history) >= 7:
            change_7d = round(((price_history[-1]["price"] / price_history[-7]["price"]) - 1) * 100, 2) if price_history[-7]["price"] > 0 else 0
        if len(price_history) >= 30:
            change_30d = round(((price_history[-1]["price"] / price_history[-30]["price"]) - 1) * 100, 2) if price_history[-30]["price"] > 0 else 0
        if len(price_history) >= 2:
            change_90d = round(((price_history[-1]["price"] / price_history[0]["price"]) - 1) * 100, 2) if price_history[0]["price"] > 0 else 0
        
        # Technical indicators for cards with enough history
        technicals = {}
        if len(price_history) >= 14:
            technicals = compute_technical_indicators(price_history)
        
        card_analytics.append({
            "name": card["name"],
            "set_code": card["set_code"],
            "set_name": card["set_name"],
            "collector_number": card["collector_number"],
            "foil": card["foil"],
            "rarity": card["rarity"],
            "quantity": card["quantity"],
            "scryfall_id": card["scryfall_id"],
            "binder": card["binder"],
            "finish": card["finish"],
            "purchase_price": card["purchase_price"],
            "current_price": current_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "change_7d": change_7d,
            "change_30d": change_30d,
            "change_90d": change_90d,
            "price_history": price_history,
            "vendor_prices": vendor_prices_current,
            "technicals": technicals,
        })
    
    # Summary stats
    current_total = sum((c["current_price"] or 0) * c["quantity"] for c in card_analytics)
    priced_count = sum(1 for c in card_analytics if c["current_price"] is not None)
    
    # Binder and rarity summaries
    binder_summary = defaultdict(lambda: {"count": 0, "purchase": 0, "current": 0})
    rarity_summary = defaultdict(lambda: {"count": 0, "value": 0})
    
    for ca in card_analytics:
        b = ca["binder"]
        binder_summary[b]["count"] += ca["quantity"]
        binder_summary[b]["purchase"] += ca["purchase_price"] * ca["quantity"]
        binder_summary[b]["current"] += (ca["current_price"] or 0) * ca["quantity"]
        
        r = ca["rarity"]
        rarity_summary[r]["count"] += ca["quantity"]
        rarity_summary[r]["value"] += (ca["current_price"] or 0) * ca["quantity"]
    
    portfolio = {
        "total_purchase": round(total_purchase, 2),
        "total_current": round(current_total, 2),
        "total_pnl": round(current_total - total_purchase, 2),
        "total_pnl_pct": round(((current_total / total_purchase) - 1) * 100, 2) if total_purchase > 0 else 0,
        "card_count": sum(c["quantity"] for c in cards),
        "unique_cards": len(set(c["name"] for c in cards)),
        "priced_cards": priced_count,
        "latest_date": latest_date,
        "date_range": {"start": all_dates[0], "end": all_dates[-1]},
        "portfolio_values": portfolio_values,
        "binder_summary": dict(binder_summary),
        "rarity_summary": dict(rarity_summary),
    }
    
    print(f"  Portfolio: ${total_purchase:,.2f} purchase → ${current_total:,.2f} current")
    print(f"  P&L: ${current_total - total_purchase:,.2f} ({portfolio['total_pnl_pct']:.1f}%)")
    print(f"  Cards with prices: {priced_count}/{len(card_analytics)}")
    
    return portfolio, card_analytics


def find_arbitrage(card_analytics):
    """Find cross-vendor price gaps."""
    print("🔍 Finding arbitrage opportunities...")
    
    opportunities = []
    seen = set()
    
    for card in card_analytics:
        vp = card.get("vendor_prices", {})
        if not vp or card["name"] in seen:
            continue
        
        finish = card["finish"]
        tcg = vp.get(f"tcgplayer_retail_{finish}")
        ck = vp.get(f"cardkingdom_retail_{finish}")
        ck_buy = vp.get(f"cardkingdom_buylist_{finish}")
        cm = vp.get(f"cardmarket_retail_{finish}")
        
        if tcg and ck and min(tcg, ck) > 2:
            spread = abs(tcg - ck)
            spread_pct = (spread / min(tcg, ck)) * 100
            
            if spread_pct > 15:
                cheaper = "tcgplayer" if tcg < ck else "cardkingdom"
                opportunities.append({
                    "name": card["name"],
                    "set_code": card["set_code"],
                    "foil": card["foil"],
                    "scryfall_id": card["scryfall_id"],
                    "tcg_retail": tcg,
                    "ck_retail": ck,
                    "ck_buylist": ck_buy,
                    "cm_retail": cm,
                    "spread_pct": round(spread_pct, 1),
                    "cheaper_vendor": cheaper,
                    "binder": card["binder"],
                })
                seen.add(card["name"])
    
    opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
    print(f"  Found {len(opportunities)} opportunities (>15% spread, >$2)")
    return opportunities[:200]


def build_buylist_margins(card_analytics):
    """Surface CardKingdom buylist vs best retail — the LGS 'Buylist Sanity Check' wedge."""
    print("🏪 Building buylist-vs-retail margins...")

    margins = []

    for card in card_analytics:
        vp = card.get("vendor_prices", {})
        if not vp:
            continue

        finish = card["finish"]
        ck_buylist = vp.get(f"cardkingdom_buylist_{finish}")
        if not ck_buylist or ck_buylist <= 0:
            continue

        retail_options = [
            ("tcgplayer", vp.get(f"tcgplayer_retail_{finish}")),
            ("cardkingdom", vp.get(f"cardkingdom_retail_{finish}")),
            ("cardmarket", vp.get(f"cardmarket_retail_{finish}")),
        ]
        retail_options = [(v, p) for v, p in retail_options if p]
        if not retail_options:
            continue

        retail_vendor, best_retail = max(retail_options, key=lambda x: x[1])

        margin_abs = best_retail - ck_buylist
        margin_pct = margin_abs / ck_buylist * 100

        margins.append({
            "name": card["name"],
            "set_code": card["set_code"],
            "foil": card["foil"],
            "scryfall_id": card["scryfall_id"],
            "binder": card["binder"],
            "quantity": card["quantity"],
            "best_retail": round(best_retail, 2),
            "retail_vendor": retail_vendor,
            "ck_buylist": round(ck_buylist, 2),
            "margin_abs": round(margin_abs, 2),
            "margin_pct": round(margin_pct, 1),
        })

    margins.sort(key=lambda x: x["margin_pct"], reverse=True)
    print(f"  Found {len(margins)} cards with buylist + retail")
    return margins[:200]


def write_output(output_dir, portfolio, card_analytics, movers=None, arbitrage=None, buylist_margins=None):
    """Write all output JSON files to the specified directory."""
    print("\n💾 Writing output files...")
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "portfolio.json"), "w") as f:
        json.dump(portfolio, f)
    print(f"  portfolio.json: {os.path.getsize(os.path.join(output_dir, 'portfolio.json')) / 1024:.0f}KB")
    
    # Cards summary (no history/technicals for table view)
    cards_summary = []
    cards_detail = {}
    
    for ca in card_analytics:
        summary = {k: v for k, v in ca.items() if k not in ("price_history", "vendor_prices", "technicals")}
        cards_summary.append(summary)
        
        if ca["price_history"]:
            cards_detail[ca["scryfall_id"]] = {
                "name": ca["name"],
                "set_code": ca["set_code"],
                "foil": ca["foil"],
                "purchase_price": ca["purchase_price"],
                "history": ca["price_history"],
                "vendor_prices": ca.get("vendor_prices", {}),
                "technicals": ca.get("technicals", {}),
            }
    
    with open(os.path.join(output_dir, "cards.json"), "w") as f:
        json.dump(cards_summary, f)
    print(f"  cards.json: {os.path.getsize(os.path.join(output_dir, 'cards.json')) / 1024:.0f}KB")
    
    with open(os.path.join(output_dir, "price_history.json"), "w") as f:
        json.dump(cards_detail, f)
    size_mb = os.path.getsize(os.path.join(output_dir, "price_history.json")) / 1024 / 1024
    print(f"  price_history.json: {size_mb:.1f}MB")
    
    if movers is not None:
        with open(os.path.join(output_dir, "movers.json"), "w") as f:
            json.dump(movers, f)
        print(f"  movers.json: {os.path.getsize(os.path.join(output_dir, 'movers.json')) / 1024:.0f}KB")
    
    if arbitrage is not None:
        with open(os.path.join(output_dir, "arbitrage.json"), "w") as f:
            json.dump(arbitrage, f)
        print(f"  arbitrage.json: {os.path.getsize(os.path.join(output_dir, 'arbitrage.json')) / 1024:.0f}KB")

    if buylist_margins is not None:
        with open(os.path.join(output_dir, "buylist_margins.json"), "w") as f:
            json.dump(buylist_margins, f)
        print(f"  buylist_margins.json: {os.path.getsize(os.path.join(output_dir, 'buylist_margins.json')) / 1024:.0f}KB")

    print(f"\n✅ Preprocessing complete!")
    print(f"   Output: {output_dir}")
    print(f"   Cards with tech indicators: {sum(1 for c in cards_detail.values() if c.get('technicals'))}")


def main():
    parser = argparse.ArgumentParser(description="Mana Vault — Data Preprocessor")
    parser.add_argument("--csv", help="Path to ManaBox collection CSV (default: ManaBox_Collection.csv)")
    parser.add_argument("--output", help="Output directory for JSON files (default: dashboard/public/data/)")
    args = parser.parse_args()
    
    output_dir = args.output or OUTPUT_DIR
    per_user = args.csv is not None
    
    print("=" * 60)
    print("🃏 Mana Vault — Data Preprocessor")
    if per_user:
        print(f"   Mode: per-user (CSV: {args.csv})")
        print(f"   Output: {output_dir}")
    print("=" * 60)
    
    cards = load_collection(csv_path=args.csv)
    prices = extract_prices_fast(cards)
    portfolio, card_analytics = build_portfolio_analytics(cards, prices)
    arbitrage = find_arbitrage(card_analytics)
    buylist_margins = build_buylist_margins(card_analytics)

    # Movers only in default mode (they're global, not per-user)
    movers = None
    if not per_user:
        movers = parse_mtgstocks_movers(cards)

    write_output(output_dir, portfolio, card_analytics, movers=movers, arbitrage=arbitrage, buylist_margins=buylist_margins)


if __name__ == "__main__":
    main()
