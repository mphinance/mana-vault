#!/usr/bin/env python3
"""
MTG Portfolio Tracker — Tournament & Event Scraper
Scrapes upcoming events from magic.gg and recent results from MTGTop8.
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DATA_DIR, "dashboard", "public", "data")

# ─────────────────────────────────────────
# magic.gg schedule scraper
# ─────────────────────────────────────────
def scrape_magic_gg_schedule(page):
    """Scrape upcoming events from magic.gg/schedule."""
    print("📅 Scraping magic.gg/schedule...")

    page.goto("https://magic.gg/schedule", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    events = []
    seen = set()

    # Extract all event links from the schedule page
    links = page.query_selector_all("a[href]")
    for link in links:
        try:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""

            if not text or len(text) < 10:
                continue

            # Skip nav/footer/generic links
            if any(skip in href for skip in ["mtgarena", "mtgo", "wizards.com/en/products",
                                              "support.wizards", "company.wizards", "ketch",
                                              "privacy", "conduct", "fancon", "#"]):
                continue
            skip_texts = ["mtg arena", "tabletop magic", "magic online",
                          "customer service", "privacy", "terms",
                          "store champion", "qualifier weekend",
                          "magic.gg logo", "events", "schedule",
                          "play", "products", "news", "sign in", "log in",
                          "formats", "magic play", "cookie"]
            if any(skip == text.lower().strip() or skip in text.lower() for skip in skip_texts
                   if len(skip) > 3):
                continue
            # Must look like an actual event — require either a date or event keyword
            has_date = bool(re.search(r'\d{4}|\w+\s+\d+', text))
            has_keyword = any(kw in text.lower() for kw in
                              ["championship", "regional", "pro tour", "spotlight",
                               "magiccon", "pax", "open", "challenge", "cup",
                               "series", "experience", "convention", "rcq",
                               "nrg", "paupergeddon"])
            if not has_date and not has_keyword:
                continue

            # Parse date from text: "Event Name - Month Day–Day, Year - Location"
            date_match = re.search(
                r'(\w+ \d+)[–\-](\d+),?\s*(\d{4})',
                text
            )
            date_str = ""
            if date_match:
                date_str = f"{date_match.group(1)}-{date_match.group(2)}, {date_match.group(3)}"

            # Deduplicate
            key = text[:60]
            if key in seen:
                continue
            seen.add(key)

            # Detect event type
            event_type = "event"
            text_lower = text.lower()
            if "pro tour" in text_lower:
                event_type = "pro_tour"
            elif "regional" in text_lower or " rc " in text_lower:
                event_type = "regional"
            elif "spotlight" in text_lower:
                event_type = "spotlight"
            elif "magiccon" in text_lower:
                event_type = "magiccon"
            elif "championship" in text_lower or "champions cup" in text_lower:
                event_type = "championship"
            elif "pax" in text_lower or "experience" in text_lower:
                event_type = "convention"
            elif "open" in text_lower:
                event_type = "open"

            # Build full URL
            if href.startswith("/"):
                href = f"https://magic.gg{href}"
            elif not href.startswith("http"):
                href = f"https://magic.gg/{href}"

            # Parse name and location from text
            # Text format: "Event Name - Date - Location" or "Event Name - Location"
            # Remove the date portion from the text first to isolate name and location
            clean_text = text
            if date_match:
                # Remove the date portion (e.g., "March 6–8, 2026")
                clean_text = re.sub(r'\s*-?\s*\w+ \d+[–\-]\d+,?\s*\d{4}\s*-?\s*', ' - ', text).strip(' -')

            parts = clean_text.rsplit(" - ", 1)
            name = parts[0].strip()
            location = parts[1].strip() if len(parts) > 1 else ""

            # Skip undated generic series pages (e.g., "Magic Spotlight Series", "World Championship")
            if not date_str and not location:
                continue

            events.append({
                "name": name,
                "dates": date_str,
                "location": location,
                "url": href,
                "type": event_type,
                "raw_text": text[:120],
            })
        except Exception:
            continue

    print(f"  Found {len(events)} events")
    return events


# ─────────────────────────────────────────
# MTGTop8 scraper
# ─────────────────────────────────────────
FORMATS = {
    "ST": "Standard",
    "MO": "Modern",
    "PI": "Pioneer",
}


def scrape_mtgtop8_format(page, fmt_code, fmt_name):
    """Scrape a single format page from MTGTop8."""
    print(f"  📊 {fmt_name} (/{fmt_code})...")

    url = f"https://www.mtgtop8.com/format?f={fmt_code}"
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)

    content = page.content()
    result = {
        "format": fmt_name,
        "archetypes": [],
        "recent_events": [],
        "top_cards": [],
    }

    # Extract archetypes (links to /archetype?a=...)
    arch_links = page.query_selector_all('a[href*="archetype?a="]')
    seen_archs = set()
    for link in arch_links:
        try:
            name = link.inner_text().strip()
            href = link.get_attribute("href") or ""
            if name and name not in seen_archs:
                seen_archs.add(name)
                result["archetypes"].append({
                    "name": name,
                    "url": f"https://www.mtgtop8.com/{href}" if not href.startswith("http") else href,
                })
        except Exception:
            continue

    # Extract recent events (links to /event?e=...)
    event_links = page.query_selector_all('a[href*="event?e="]')
    seen_events = set()
    for link in event_links:
        try:
            name = link.inner_text().strip()
            href = link.get_attribute("href") or ""
            eid_match = re.search(r'e=(\d+)', href)
            eid = eid_match.group(1) if eid_match else ""

            if not name or eid in seen_events or len(name) < 3:
                continue
            seen_events.add(eid)

            full_url = f"https://www.mtgtop8.com/{href}" if not href.startswith("http") else href

            result["recent_events"].append({
                "name": name,
                "event_id": eid,
                "format": fmt_name,
                "url": full_url,
            })
        except Exception:
            continue

    # Extract top cards (links to mtgpics with % text)
    # The page shows top cards with percentage like "55 %"
    pct_links = page.query_selector_all('a[href*="mtgpics.com"]')
    for link in pct_links:
        try:
            text = link.inner_text().strip()
            pct_match = re.match(r'(\d+)\s*%', text)
            if pct_match:
                # Get card image/name from nearby elements
                result["top_cards"].append({
                    "frequency_pct": int(pct_match.group(1)),
                    "url": link.get_attribute("href") or "",
                })
        except Exception:
            continue

    return result


def scrape_mtgtop8(page):
    """Scrape all configured formats from MTGTop8."""
    print("🏆 Scraping MTGTop8...")

    results = {}
    for fmt_code, fmt_name in FORMATS.items():
        try:
            results[fmt_name] = scrape_mtgtop8_format(page, fmt_code, fmt_name)
            time.sleep(1)  # Be polite
        except Exception as e:
            print(f"    ⚠ Failed {fmt_name}: {e}")
            results[fmt_name] = {"format": fmt_name, "archetypes": [], "recent_events": [], "top_cards": []}

    return results


# ─────────────────────────────────────────
# Collection cross-reference
# ─────────────────────────────────────────
def load_collection_names():
    """Load card names from ManaBox CSV for cross-referencing."""
    csv_path = os.path.join(DATA_DIR, "ManaBox_Collection.csv")
    if not os.path.exists(csv_path):
        return set()

    names = set()
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            names.add(row["Name"].lower().strip())
    return names


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    quick_mode = "--quick" in sys.argv

    print("=" * 60)
    print("🃏 MTG Portfolio Tracker — Event Scraper")
    print("=" * 60)
    print(f"  Mode: {'QUICK (schedule only)' if quick_mode else 'FULL (schedule + MTGTop8)'}")
    print()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "MTGPortfolioTracker/1.0"})

        # Scrape magic.gg schedule
        try:
            upcoming = scrape_magic_gg_schedule(page)
        except Exception as e:
            print(f"  ⚠ magic.gg scrape failed: {e}")
            upcoming = []

        # Scrape MTGTop8
        metagame = {}
        if not quick_mode:
            try:
                metagame = scrape_mtgtop8(page)
            except Exception as e:
                print(f"  ⚠ MTGTop8 scrape failed: {e}")

        browser.close()

    # Collect all recent events across formats
    recent_events = []
    all_archetypes = {}
    for fmt_name, data in metagame.items():
        recent_events.extend(data.get("recent_events", []))
        if data.get("archetypes"):
            all_archetypes[fmt_name] = data["archetypes"][:10]  # Top 10 per format

    # Cross-reference with collection
    collection_names = load_collection_names()
    for fmt_name, archs in all_archetypes.items():
        for arch in archs:
            arch["in_collection"] = arch["name"].lower().strip() in collection_names

    # Build output
    output = {
        "upcoming": upcoming,
        "recent_events": recent_events[:50],  # Cap
        "metagame": all_archetypes,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
    }

    # Write
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "events.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"\n💾 events.json: {size_kb:.0f}KB")
    print(f"   {len(upcoming)} upcoming events")
    print(f"   {len(recent_events)} recent tournament results")
    print(f"   {len(all_archetypes)} format metagames")
    print("\n✅ Event scraping complete!")


if __name__ == "__main__":
    main()
