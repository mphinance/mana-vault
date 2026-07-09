#!/usr/bin/env python3
"""
MTG Portfolio Tracker — Data Updater
Downloads fresh price data from MTGJSON and re-runs the preprocessor.

Usage:
    python3 update.py              # Quick: AllPricesToday.json only (~50MB)
    python3 update.py --full       # Full:  AllPricesToday + AllPrices.json.bz2 (~95MB compressed)
"""

import bz2
import os
import shutil
import subprocess
import sys
import time
import urllib.request

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://mtgjson.com/api/v5"

# Files to download — (url_path, local_filename, decompress_bz2)
QUICK_FILES = [
    (f"{BASE_URL}/AllPricesToday.json", "AllPricesToday.json", False),
]

FULL_FILES = [
    (f"{BASE_URL}/AllPricesToday.json", "AllPricesToday.json", False),
    (f"{BASE_URL}/AllPrices.json.bz2", "AllPrices.json", True),
]


def download_file(url, dest_path, decompress=False):
    """Download a file with progress display. Optionally decompress bz2."""
    filename = os.path.basename(dest_path)
    label = f"  ⬇  {filename}"

    if decompress:
        label += " (bz2 → json)"

    print(f"{label}")
    print(f"     {url}")

    # Backup existing file
    if os.path.exists(dest_path):
        backup = dest_path + ".bak"
        shutil.copy2(dest_path, backup)

    start = time.time()

    req = urllib.request.Request(url, headers={"User-Agent": "MTGPortfolioTracker/1.0"})
    response = urllib.request.urlopen(req, timeout=300)
    total = int(response.headers.get("Content-Length", 0))

    if decompress:
        # Download bz2 to temp, then decompress
        tmp_path = dest_path + ".bz2.tmp"
        downloaded = 0
        with open(tmp_path, "wb") as f:
            while True:
                chunk = response.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    print(f"     {pct:5.1f}%  {mb:.1f}/{total_mb:.1f} MB", end="\r")

        print(f"     Downloaded {downloaded / 1024 / 1024:.1f} MB, decompressing...")

        with open(tmp_path, "rb") as compressed:
            with open(dest_path, "wb") as out:
                decompressor = bz2.BZ2Decompressor()
                for chunk in iter(lambda: compressed.read(4 * 1024 * 1024), b""):
                    out.write(decompressor.decompress(chunk))

        os.remove(tmp_path)
    else:
        # Direct download
        downloaded = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    print(f"     {pct:5.1f}%  {mb:.1f}/{total_mb:.1f} MB", end="\r")

    elapsed = time.time() - start
    final_size = os.path.getsize(dest_path) / 1024 / 1024
    print(f"     ✅ {final_size:.1f} MB in {elapsed:.0f}s")

    # Remove backup on success
    backup = dest_path + ".bak"
    if os.path.exists(backup):
        os.remove(backup)


def main():
    full_mode = "--full" in sys.argv

    print("=" * 60)
    print("🃏 MTG Portfolio Tracker — Data Updater")
    print("=" * 60)
    print(f"  Mode: {'FULL (90-day history + today)' if full_mode else 'QUICK (today only)'}")
    print(f"  Dir:  {DATA_DIR}")
    print()

    files = FULL_FILES if full_mode else QUICK_FILES

    print("📥 Downloading from MTGJSON...")
    for url, filename, decompress in files:
        dest = os.path.join(DATA_DIR, filename)
        try:
            download_file(url, dest, decompress)
        except Exception as e:
            print(f"     ❌ Failed: {e}")
            # Restore backup if available
            backup = dest + ".bak"
            if os.path.exists(backup):
                shutil.move(backup, dest)
                print(f"     ↩ Restored backup")
            sys.exit(1)

    print()
    print("🔄 Running preprocessor...")
    print("-" * 60)
    result = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "preprocess.py")],
        cwd=DATA_DIR,
    )

    if result.returncode != 0:
        print("\n❌ Preprocessor failed!")
        sys.exit(1)

    # Fire price alerts off the fresh signals (best-effort — never fails the update)
    print()
    print("🔔 Checking price alerts...")
    print("-" * 60)
    alerts_result = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "alerts.py")],
        cwd=DATA_DIR,
    )
    if alerts_result.returncode != 0:
        print("⚠ Alerts step failed (non-fatal) — data is still fresh.")

    print()
    print("=" * 60)
    print("✅ Update complete! Dashboard data is fresh.")
    print("   Run: cd dashboard && npm run dev")
    print("=" * 60)


if __name__ == "__main__":
    main()
