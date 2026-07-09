#!/usr/bin/env python3
"""
Mana Vault — Price Alerts Engine

Diffs each card's latest technical signal against a saved snapshot and emits
only the NEW fires since the last run. The signal engine already runs daily in
preprocess.py's compute_technical_indicators(); this script is the notification
pipe on top of it (see reference/strategist-memo.md §2 #1).

Reads:  dashboard/public/data/price_history.json
        (optional) dashboard/public/data/cards.json  — for binder + price fallback
State:  dashboard/public/data/alerts_state.json      — last-seen signal per card
Writes: dashboard/public/data/alerts.json            — new fires this run

Usage:
  python3 alerts.py                                   # local, diff + write
  python3 alerts.py --dry-run                         # compute + print, write nothing
  python3 alerts.py --webhook https://...             # also POST a compact summary
  python3 alerts.py --data path/to/data               # custom data dir
  MANA_VAULT_WEBHOOK=https://... python3 alerts.py     # webhook via env

First run (no snapshot) seeds the snapshot and emits ZERO alerts so historical
signals are never spammed. stdlib only.
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone

DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "dashboard", "public", "data"
)


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


def latest_signal(technicals):
    """Return the newest signal dict {date, type, label} for a card, or None.

    technicals.signals is a list of {date, type, label} in chronological order
    (see preprocess.py compute_technical_indicators). We pick the entry with the
    max date; ties break to the last one appended (later in the array).
    """
    if not isinstance(technicals, dict):
        return None
    signals = technicals.get("signals")
    if not signals:
        return None
    best = None
    for sig in signals:
        if not isinstance(sig, dict) or "date" not in sig:
            continue
        if best is None or sig["date"] >= best["date"]:
            best = sig
    return best


def fingerprint(signal):
    """Stable identity for a signal: '{type}@{date}'."""
    return f"{signal.get('type')}@{signal.get('date')}"


def current_price_for(detail, card_summary):
    """Null-safe current price: last history entry, else cards.json current_price."""
    history = detail.get("history") if isinstance(detail, dict) else None
    if history:
        last = history[-1]
        if isinstance(last, dict) and last.get("price") is not None:
            return last["price"]
    if isinstance(card_summary, dict) and card_summary.get("current_price") is not None:
        return card_summary["current_price"]
    return None


def compute_alerts(price_history, cards_by_id, prev_state):
    """Diff latest signals against prev_state. Returns (alerts, new_state).

    new_state maps scryfall_id -> latest fingerprint for every card that has a
    signal (so the snapshot always reflects reality). alerts contains only cards
    whose latest fingerprint differs from prev_state (i.e. a new fire).
    """
    alerts = []
    new_state = {}
    first_run = not prev_state

    for scryfall_id, detail in price_history.items():
        if not isinstance(detail, dict):
            continue
        sig = latest_signal(detail.get("technicals"))
        if sig is None:
            continue

        fp = fingerprint(sig)
        new_state[scryfall_id] = fp

        # Seed-only on first run; otherwise fire when the fingerprint changed.
        if first_run:
            continue
        if prev_state.get(scryfall_id) == fp:
            continue

        summary = cards_by_id.get(scryfall_id, {})
        alerts.append(
            {
                "scryfall_id": scryfall_id,
                "name": detail.get("name") or summary.get("name"),
                "set_code": detail.get("set_code") or summary.get("set_code"),
                "foil": detail.get("foil", summary.get("foil", False)),
                "type": sig.get("type"),
                "label": sig.get("label"),
                "date": sig.get("date"),
                "current_price": current_price_for(detail, summary),
                "binder": summary.get("binder"),
            }
        )

    # Newest date first (fall back to empty string so None never crashes sort).
    alerts.sort(key=lambda a: a.get("date") or "", reverse=True)
    return alerts, new_state, first_run


def post_webhook(url, payload):
    """POST a compact JSON summary via stdlib urllib. Best-effort, never raises."""
    body = json.dumps(payload).encode("utf-8")
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
        description="Emit new MTG price-signal alerts by diffing against a snapshot."
    )
    parser.add_argument(
        "--data", default=DEFAULT_DATA_DIR, help="Data directory (default: %(default)s)"
    )
    parser.add_argument(
        "--webhook", default=None, help="Webhook URL for a compact JSON summary"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print, but do not write snapshot/alerts or POST",
    )
    args = parser.parse_args()

    data_dir = args.data
    webhook = args.webhook or os.environ.get("MANA_VAULT_WEBHOOK")

    history_path = os.path.join(data_dir, "price_history.json")
    state_path = os.path.join(data_dir, "alerts_state.json")
    alerts_path = os.path.join(data_dir, "alerts.json")
    cards_path = os.path.join(data_dir, "cards.json")

    price_history = load_json(history_path)
    if not price_history:
        print(f"ℹ️  No price_history.json at {history_path} — nothing to alert on.")
        print("   Run preprocess.py first to generate collection data. Exiting cleanly.")
        return 0

    # cards.json is optional — only used for binder + a price fallback.
    cards_summary = load_json(cards_path) or []
    cards_by_id = {
        c["scryfall_id"]: c
        for c in cards_summary
        if isinstance(c, dict) and c.get("scryfall_id")
    }

    prev_state = load_json(state_path) or {}
    alerts, new_state, first_run = compute_alerts(
        price_history, cards_by_id, prev_state
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {"generated_at": generated_at, "count": len(alerts), "alerts": alerts}

    if first_run:
        print(
            f"🌱 First run: seeded snapshot for {len(new_state)} cards, "
            "emitted 0 alerts (no historical spam)."
        )
    else:
        print(f"🔔 {len(alerts)} new alert(s) since last snapshot.")
        for a in alerts:
            price = a["current_price"]
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "n/a"
            print(f"  • {a['name']} [{a['set_code']}] {a['label']} ({a['date']}) {price_str}")

    if args.dry_run:
        print("🧪 Dry run — not writing snapshot/alerts or posting webhook.")
        return 0

    with open(alerts_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"💾 Wrote {alerts_path} ({len(alerts)} alerts)")

    with open(state_path, "w") as f:
        json.dump(new_state, f, indent=2)
    print(f"💾 Wrote {state_path} ({len(new_state)} cards tracked)")

    if webhook and alerts:
        post_webhook(
            webhook,
            {
                "text": f"Mana Vault: {len(alerts)} new price signal(s)",
                "generated_at": generated_at,
                "count": len(alerts),
                "alerts": alerts,
            },
        )
    elif webhook:
        print("📭 Webhook configured but no new alerts — skipping POST.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
