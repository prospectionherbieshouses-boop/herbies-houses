"""
main.py — API FastAPI pour Herbies Houses.

Routes :
    GET  /listings          — retourne les annonces analysées
    POST /scrape            — lance le scraper Centris en arrière-plan
    POST /analyze           — analyse une annonce (cashflow + score)
    GET  /health            — statut de l'API
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Chemins relatifs au fichier main.py
BASE_DIR    = os.path.dirname(os.path.dirname(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
SCRAPER_DIR = os.path.join(BASE_DIR, "scraper")
LISTINGS_FILE = os.path.join(DATA_DIR, "listings.json")

# Ajouter scraper/ et backend/ au path Python
sys.path.insert(0, SCRAPER_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import analyze_all, analyze_listing, calculate_cashflow

app = FastAPI(title="Herbies API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)

# État du scraper (simple, en mémoire)
scraper_status = {"running": False, "last_run": None, "count": 0, "error": None}


# ── Modèles ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    price: int
    units: int
    address: Optional[str] = ""
    declared_income: Optional[int] = None
    down_pct: Optional[float] = 0.20
    rate: Optional[float] = 0.0469
    years: Optional[int] = 25


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_listings() -> list[dict]:
    if not os.path.exists(LISTINGS_FILE):
        return []
    with open(LISTINGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_listings(listings: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LISTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)


def _run_scraper() -> None:
    """Tâche en arrière-plan : scraper + analyser + sauvegarder."""
    global scraper_status
    scraper_status["running"] = True
    scraper_status["error"]   = None

    try:
        from scraper import run as scrape
        raw_listings = scrape(max_price=2_000_000)
        analyzed     = analyze_all(raw_listings)
        _save_listings(analyzed)
        scraper_status["count"]    = len(analyzed)
        scraper_status["last_run"] = datetime.now().isoformat()
    except Exception as e:
        scraper_status["error"] = str(e)
        print(f"[Scraper] Erreur : {e}")
    finally:
        scraper_status["running"] = False


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/listings")
def get_listings(
    min_cashflow: int = 0,
    min_score: int = 0,
    max_price: int = 2_000_000,
    sort_by: str = "score",
):
    """Retourne les annonces filtrées et triées."""
    listings = _load_listings()

    # Si non encore analysées, les analyser à la volée
    if listings and "cashflow_monthly" not in listings[0]:
        listings = analyze_all(listings)
        _save_listings(listings)

    # Filtres
    results = [
        l for l in listings
        if l.get("cashflow_monthly", -9999) >= min_cashflow
        and l.get("score", 0) >= min_score
        and l.get("price", 0) <= max_price
    ]

    # Tri
    valid_sorts = {"score", "cashflow_monthly", "price", "cap_rate_pct", "mrb"}
    key = sort_by if sort_by in valid_sorts else "score"
    reverse = key != "mrb"  # MRB : plus bas = mieux
    results.sort(key=lambda x: x.get(key, 0), reverse=reverse)

    return {
        "count":    len(results),
        "listings": results,
        "scraped_at": scraper_status.get("last_run"),
    }


@app.post("/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    """Lance le scraper en arrière-plan."""
    if scraper_status["running"]:
        raise HTTPException(status_code=409, detail="Scraper déjà en cours")
    background_tasks.add_task(_run_scraper)
    return {"message": "Scraping lancé", "status": scraper_status}


@app.get("/scrape/status")
def scrape_status():
    """Retourne le statut actuel du scraper."""
    return scraper_status


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Calcule le cashflow et le score pour une propriété donnée."""
    listing = {
        "price":           req.price,
        "units":           req.units,
        "address":         req.address or "",
        "declared_income": req.declared_income,
    }
    result = calculate_cashflow(
        price           = req.price,
        units           = req.units,
        address         = req.address or "",
        declared_income = req.declared_income,
        down_pct        = req.down_pct,
        rate            = req.rate,
        years           = req.years,
    )
    from analyzer import score_deal
    result["score"] = score_deal(result)
    return result
