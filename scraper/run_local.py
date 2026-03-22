"""
run_local.py — Lance le scraper Centris localement et envoie les résultats à Railway.

Usage :
    python run_local.py
    ou double-cliquer sur scraper.bat
"""

import json
import sys
import os
import requests
from pathlib import Path

# URL du backend Railway
RAILWAY_URL = "https://web-production-ca9a1.up.railway.app"

# Ajouter le dossier scraper au path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from centris import scrape_centris
from analyzer import analyze_all


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

    print(f"  {len(listings)} annonces récupérées")
    print()

    # 2. Analyser le cashflow
    print("Étape 2 — Analyse cashflow...")
    analyzed = analyze_all(listings)
    print(f"  {len(analyzed)} annonces analysées")
    print()

    # 3. Sauvegarder localement
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    local_file = data_dir / "listings.json"
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2)
    print(f"  Sauvegardé localement : {local_file}")
    print()

    # 4. Envoyer à Railway
    print("Étape 3 — Envoi vers Railway...")
    try:
        resp = requests.post(
            f"{RAILWAY_URL}/listings/import",
            json={"listings": analyzed},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  {result['message']}")
    except Exception as e:
        print(f"  Erreur envoi Railway : {e}")
        print("  Les données sont quand même sauvegardées localement.")
        return

    print()
    print("=" * 50)
    cashflow_positif = [l for l in analyzed if l.get("cashflow_monthly", 0) > 200]
    print(f"  TOTAL       : {len(analyzed)} annonces")
    print(f"  Cashflow +  : {len(cashflow_positif)} deals intéressants")
    if analyzed:
        top = sorted(analyzed, key=lambda x: x.get("score", 0), reverse=True)[:3]
        print()
        print("  Top 3 deals :")
        for i, l in enumerate(top, 1):
            print(f"  {i}. {l.get('address', 'N/A')} — {l.get('type', '')} — ${l.get('price', 0):,} — cashflow {l.get('cashflow_monthly', 0):+,.0f}$/mois")
    print("=" * 50)
    print()
    print(f"Voir les résultats : https://prospectionherbieshouses-boop.github.io/herbies-houses/")


if __name__ == "__main__":
    main()
