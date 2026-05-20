"""
Mana Vault API — Minimal backend for multi-user collection management.

Endpoints:
  GET  /api/health              Health check
  POST /api/upload              Upload ManaBox CSV → generate vault
  GET  /api/export/{slug}       Download original CSV
  GET  /api/vaults              List all vaults (public)
  GET  /api/vaults/{slug}/status  Check processing status
"""

import asyncio
import json
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Mana Vault API", version="1.0.0")

# CORS — allow the dashboard origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Venus serves both, but allow dev too
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.environ.get("MANA_VAULT_BASE", "/app")
USER_DATA_DIR = os.path.join(BASE_DIR, "user_data")
PREPROCESS_SCRIPT = os.path.join(BASE_DIR, "preprocess.py")

os.makedirs(USER_DATA_DIR, exist_ok=True)


def slugify(text: str) -> str:
    """Generate a URL-safe slug from text."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text or "vault"


def make_unique_slug(name: str) -> str:
    """Generate a unique slug, appending a number if it already exists."""
    base = slugify(name)
    slug = base
    counter = 2
    while os.path.exists(os.path.join(USER_DATA_DIR, slug)):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


@app.get("/api/health")
async def health():
    vault_count = sum(
        1 for d in os.listdir(USER_DATA_DIR)
        if os.path.isdir(os.path.join(USER_DATA_DIR, d))
    ) if os.path.exists(USER_DATA_DIR) else 0
    return {"status": "ok", "vaults": vault_count, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/upload")
async def upload_collection(
    file: UploadFile = File(...),
    name: str = Form("My Vault"),
):
    """Upload a ManaBox CSV and create a new vault."""
    # Validate file
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")

    content = await file.read()
    if len(content) > 50_000_000:  # 50MB limit
        raise HTTPException(400, "File too large (max 50MB)")

    if len(content) < 50:
        raise HTTPException(400, "File appears to be empty")

    # Generate unique slug
    slug = make_unique_slug(name)
    vault_dir = os.path.join(USER_DATA_DIR, slug)
    data_dir = os.path.join(vault_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Save CSV
    csv_path = os.path.join(vault_dir, "collection.csv")
    with open(csv_path, "wb") as f:
        f.write(content)

    # Count cards in CSV for metadata
    lines = content.decode("utf-8", errors="ignore").strip().split("\n")
    card_count = max(0, len(lines) - 1)  # subtract header

    # Save metadata
    meta = {
        "name": name,
        "slug": slug,
        "created": datetime.utcnow().isoformat(),
        "card_count": card_count,
        "original_filename": file.filename,
        "status": "processing",
    }
    with open(os.path.join(vault_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Run preprocessor in background
    asyncio.create_task(_run_preprocess(slug, csv_path, data_dir, vault_dir))

    return {
        "slug": slug,
        "name": name,
        "card_count": card_count,
        "status": "processing",
        "vault_url": f"/?vault={slug}",
    }


async def _run_preprocess(slug: str, csv_path: str, data_dir: str, vault_dir: str):
    """Run preprocess.py as a subprocess for a user's collection."""
    meta_path = os.path.join(vault_dir, "meta.json")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", PREPROCESS_SCRIPT,
            "--csv", csv_path,
            "--output", data_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # Update metadata
        with open(meta_path) as f:
            meta = json.load(f)

        if proc.returncode == 0:
            meta["status"] = "ready"
            meta["processed_at"] = datetime.utcnow().isoformat()
            # Get actual card count from output
            cards_path = os.path.join(data_dir, "cards.json")
            if os.path.exists(cards_path):
                with open(cards_path) as f:
                    cards_data = json.load(f)
                meta["card_count"] = len(cards_data)
        else:
            meta["status"] = "error"
            meta["error"] = stderr.decode("utf-8", errors="ignore")[-500:]

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    except Exception as e:
        with open(meta_path) as f:
            meta = json.load(f)
        meta["status"] = "error"
        meta["error"] = str(e)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)


@app.get("/api/vaults/{slug}/status")
async def vault_status(slug: str):
    """Check processing status of a vault."""
    meta_path = os.path.join(USER_DATA_DIR, slug, "meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(404, "Vault not found")

    with open(meta_path) as f:
        meta = json.load(f)
    return meta


@app.get("/api/vaults")
async def list_vaults():
    """List all available vaults."""
    vaults = []
    if not os.path.exists(USER_DATA_DIR):
        return {"vaults": []}

    for slug in sorted(os.listdir(USER_DATA_DIR)):
        meta_path = os.path.join(USER_DATA_DIR, slug, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            vaults.append({
                "slug": meta.get("slug", slug),
                "name": meta.get("name", slug),
                "card_count": meta.get("card_count", 0),
                "status": meta.get("status", "unknown"),
                "created": meta.get("created"),
            })
    return {"vaults": vaults}


@app.get("/api/export/{slug}")
async def export_collection(slug: str):
    """Download the original ManaBox CSV for a vault."""
    csv_path = os.path.join(USER_DATA_DIR, slug, "collection.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(404, "Vault not found")

    # Get display name for filename
    meta_path = os.path.join(USER_DATA_DIR, slug, "meta.json")
    filename = f"{slug}_collection.csv"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        filename = f"{meta.get('name', slug)}_collection.csv"

    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename=filename,
    )
