#!/usr/bin/env python3
"""
Mana Vault — Daily Digest Generator

Rolls up the day's signal outputs into a single human-readable Markdown digest:
top movers, new price alerts, and the best buylist-vs-retail margins. It is a
read-only sibling of alerts.py — it consumes what preprocess.py and alerts.py
already produced and never modifies them.

Reads (all optional, all in dashboard/public/data/):
  movers.json          — flat list from preprocess.py parse_mtgstocks_movers
  alerts.json          — {generated_at, count, alerts[]} from alerts.py
  buylist_margins.json — flat list from preprocess.py build_buylist_margins
Writes: dashboard/public/data/digest.md

Usage:
  python3 newsletter.py                                   # build, write, print
  python3 newsletter.py --dry-run                         # build + print, write nothing
  python3 newsletter.py --webhook https://...             # also POST the markdown
  python3 newsletter.py --data path/to/data               # custom data dir
  MANA_VAULT_DIGEST_WEBHOOK=https://... python3 newsletter.py  # webhook via env

Missing/empty inputs degrade to a friendly "nothing today" digest and exit 0.
stdlib only.
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone

DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "dashboard", "public", "data"
)

MOVERS_LIMIT = 10
BUYLIST_LIMIT = 10


def load_json(path):
    """Load a JSON file, returning None if it is missing or unreadable."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Could not parse {os.path.basename(path)}: {e}")
        return None


def fmt_price(price):
    """Null-safe price formatter: '$12.34' or 'n/a'."""
    if isinstance(price, (int, float)):
        return f"${price:.2f}"
    return "n/a"


def fmt_pct(pct):
    """Null-safe percent formatter with sign: '+4.2%' / '-1.0%' / 'n/a'."""
    if isinstance(pct, (int, float)):
        return f"{pct:+.1f}%"
    return "n/a"


def card_label(name, set_code, foil):
    """'Name [SET] (foil)' — resilient to missing set/foil."""
    label = name or "Unknown card"
    if set_code:
        label += f" [{set_code}]"
    if foil:
        label += " (foil)"
    return label


def build_movers_section(movers):
    """Markdown for the top movers section. movers is a flat list or None."""
    lines = ["## 📡 Today's Top Movers", ""]
    if not movers:
        lines.append("_Nothing today — no movers data available._")
        return lines

    top = movers[:MOVERS_LIMIT]
    for m in top:
        if not isinstance(m, dict):
            continue
        label = card_label(m.get("name"), m.get("set_code"), m.get("foil"))
        price = fmt_price(m.get("price"))
        pct = fmt_pct(m.get("pct_change"))
        marker = " 🎯" if m.get("in_collection") else ""
        lines.append(f"- **{label}** — {price} ({pct}){marker}")

    if len(lines) == 2:  # header + blank, nothing appended
        lines.append("_Nothing today — no movers data available._")
    return lines


def build_alerts_section(alerts_doc):
    """Markdown for the new-alerts section. alerts_doc is alerts.json or None."""
    lines = ["## 🔔 New Alerts", ""]
    alerts = alerts_doc.get("alerts") if isinstance(alerts_doc, dict) else None
    if not alerts:
        lines.append("_Nothing today — no new alerts._")
        return lines

    for a in alerts:
        if not isinstance(a, dict):
            continue
        label = card_label(a.get("name"), a.get("set_code"), a.get("foil"))
        signal = a.get("label") or a.get("type") or "signal"
        date = a.get("date") or "—"
        price = fmt_price(a.get("current_price"))
        lines.append(f"- **{label}** — {signal} ({date}) {price}")

    if len(lines) == 2:
        lines.append("_Nothing today — no new alerts._")
    return lines


def build_buylist_section(margins):
    """Markdown for the best buylist margins section. margins is a list or None."""
    lines = ["## 🏪 Best Buylist Margins", ""]
    if not margins:
        lines.append("_Nothing today — no buylist margin data available._")
        return lines

    # Already sorted by margin_pct desc in preprocess.py; re-sort defensively.
    ranked = sorted(
        (m for m in margins if isinstance(m, dict)),
        key=lambda m: m.get("margin_pct") if isinstance(m.get("margin_pct"), (int, float)) else float("-inf"),
        reverse=True,
    )
    top = ranked[:BUYLIST_LIMIT]
    for m in top:
        label = card_label(m.get("name"), m.get("set_code"), m.get("foil"))
        retail = fmt_price(m.get("best_retail"))
        buylist = fmt_price(m.get("ck_buylist"))
        margin_pct = fmt_pct(m.get("margin_pct"))
        lines.append(f"- **{label}** — retail {retail} / buylist {buylist} → {margin_pct}")

    if len(lines) == 2:
        lines.append("_Nothing today — no buylist margin data available._")
    return lines


def build_digest(movers, alerts_doc, margins, today):
    """Assemble the full Markdown digest string."""
    lines = [f"# 🃏 Mana Vault — Daily Digest ({today})", ""]
    lines += build_movers_section(movers)
    lines.append("")
    lines += build_alerts_section(alerts_doc)
    lines.append("")
    lines += build_buylist_section(margins)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def post_webhook(url, markdown):
    """POST the digest markdown via stdlib urllib. Best-effort, never raises."""
    body = json.dumps({"content": markdown}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"📨 Webhook posted ({resp.status})")
    except Exception as e:  # noqa: BLE001 — delivery is best-effort
        print(f"⚠️  Webhook failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Build a Markdown daily digest from movers, alerts, and buylist margins."
    )
    parser.add_argument(
        "--data", default=DEFAULT_DATA_DIR, help="Data directory (default: %(default)s)"
    )
    parser.add_argument(
        "--webhook", default=None, help="Webhook URL to POST the digest markdown"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print, but do not write digest.md or POST",
    )
    args = parser.parse_args()

    data_dir = args.data
    webhook = args.webhook or os.environ.get("MANA_VAULT_DIGEST_WEBHOOK")

    movers = load_json(os.path.join(data_dir, "movers.json"))
    alerts_doc = load_json(os.path.join(data_dir, "alerts.json"))
    margins = load_json(os.path.join(data_dir, "buylist_margins.json"))

    today = datetime.now(timezone.utc).date().isoformat()
    digest = build_digest(movers, alerts_doc, margins, today)

    # A "nothing today" digest still has all three empty-state notes; treat a
    # digest with zero data across all sections as empty for webhook purposes.
    has_movers = bool(movers)
    has_alerts = bool(isinstance(alerts_doc, dict) and alerts_doc.get("alerts"))
    has_margins = bool(margins)
    is_empty = not (has_movers or has_alerts or has_margins)

    print(digest)

    if args.dry_run:
        print("🧪 Dry run — not writing digest.md or posting webhook.")
        return 0

    digest_path = os.path.join(data_dir, "digest.md")
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(digest_path, "w") as f:
            f.write(digest)
        print(f"💾 Wrote {digest_path}")
    except OSError as e:
        print(f"⚠️  Could not write {digest_path}: {e}")

    if webhook and not is_empty:
        post_webhook(webhook, digest)
    elif webhook:
        print("📭 Webhook configured but digest is empty — skipping POST.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
