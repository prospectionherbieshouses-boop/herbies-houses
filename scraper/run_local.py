"""
run_local.py — Scrape Centris et sauvegarde les résultats localement.

Usage :
    python run_local.py
    ou double-cliquer sur scraper.bat
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from centris import scrape_centris
from analyzer import analyze_all

DATA_FILE = Path(__file__).parent.parent / "app" / "listings.json"


def main():
    print("=" * 50)
    print("  Herbies Houses — Scraper local")
    print("=" * 50)
    print()

    # 1. Scraper Centris
    print("Étape 1 — Scraping Centris...")
    listings = scrape_centris(max_price=2_000_000)

    if not listings:
        print("Aucune annonce trouvée. Vérifiez votre connexion internet.")
        return

    print(f"  {len(listings)} annonces récupérées avec revenus déclarés")
    print()

    # 2. Analyser le cashflow
    print("Étape 2 — Analyse cashflow...")
    analyzed = analyze_all(listings)
    print(f"  {len(analyzed)} annonces analysées")
    print()

    # 3. Sauvegarder dans app/listings.json (lu directement par le front)
    DATA_FILE.parent.mkdir(exist_ok=True)
    payload = {
        "scraped_at": datetime.now().isoformat(),
        "count":      len(analyzed),
        "listings":   analyzed,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  Sauvegardé : {DATA_FILE}")
    print()
    print("=" * 50)

    cashflow_pos = [l for l in analyzed if l.get("cashflow_monthly", 0) > 200]
    print(f"  TOTAL      : {len(analyzed)} annonces")
    print(f"  Cashflow + : {len(cashflow_pos)} deals intéressants")

    if analyzed:
        top = sorted(analyzed, key=lambda x: x.get("score", 0), reverse=True)[:3]
        print()
        print("  Top 3 deals :")
        for i, l in enumerate(top, 1):
            cf = l.get("cashflow_monthly", 0)
            print(f"  {i}. {l.get('address','N/A')} — {l.get('type','')} — ${l.get('price',0):,} — {cf:+,.0f}$/mois")

    print("=" * 50)
    print()
    print("  Ouvre serve.bat puis va sur http://localhost:8080")


if __name__ == "__main__":
    main()
