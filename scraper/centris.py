"""
centris.py — Scrape les plex à vendre sur Centris (MLS Québec)
via leur API interne non-officielle.

Ciblage : Montréal — Rosemont, Villeray, Ahuntsic, Montréal-Nord, St-Michel
Types   : Duplex, Triplex, Quadruplex, Quintuplex

Usage :
    python centris.py
"""

import re
import json
import time
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://www.centris.ca"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.centris.ca/fr",
}

PAGE_SIZE = 20


def scrape_centris(max_price: int = 2_000_000) -> list[dict]:
    """Scrape tous les plex à vendre à Montréal via l'API Centris."""

    session = requests.Session()
    session.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Accept-Language": HEADERS["Accept-Language"],
        "Referer": BASE_URL + "/fr",
    })

    # Étape 1 — Charger la page pour obtenir les cookies de session
    print("  Connexion à Centris...")
    try:
        session.get(BASE_URL + "/fr", timeout=20)
        time.sleep(2)
    except Exception as e:
        print(f"  Erreur connexion: {e}")
        return []

    # Étape 2 — Définir la requête de recherche (plex Montréal)
    print("  Configuration de la recherche...")
    query = {
        "query": {
            "UseGeographyFilter": False,
            "Filters": [
                {
                    "Name": "Category",
                    "Values": ["Plex"]
                },
                {
                    "Name": "SalePrice",
                    "Values": ["0", str(max_price)],
                    "RangeMin": "0",
                    "RangeMax": str(max_price),
                },
            ],
            "FieldsToFacetOn": [],
            "NumberOfResults": PAGE_SIZE,
            "StartPosition": 0,
            "SortOrder": "A",
            "SortBy": "Date",
            "CarouselOffset": 0,
            "IsMapViewActive": False,
        },
        "isFullTextSearch": False,
        "includeInactive": False,
    }

    try:
        resp = session.post(
            BASE_URL + "/api/property/UpdateQuery",
            json=query,
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  Erreur UpdateQuery: {e}")
        return []

    time.sleep(2)

    # Étape 3 — Récupérer toutes les pages
    listings = []
    start = 0

    while True:
        try:
            resp = session.post(
                BASE_URL + "/Property/GetInscriptions",
                json={"startPosition": start},
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Erreur GetInscriptions (start={start}): {e}")
            break

        result     = data.get("d", {}).get("Result", {})
        html_chunk = result.get("html", "")
        count      = result.get("count", 0)

        if not html_chunk:
            html_chunk = data.get("Inscriptions", "")
            count      = data.get("count", 0)

        if not html_chunk:
            break

        soup  = BeautifulSoup(html_chunk, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item|inscription-thumbnail"))

        if not cards:
            cards = soup.find_all("article")

        if not cards:
            break

        for card in cards:
            listing = _parse_card(card)
            if listing:
                listings.append(listing)

        print(f"  Page {start // PAGE_SIZE + 1}: {len(cards)} annonces | total: {len(listings)}")

        if start + PAGE_SIZE >= count or len(cards) < PAGE_SIZE:
            break

        start += PAGE_SIZE
        time.sleep(3)  # délai anti-scraping minimum

    return listings


def _parse_card(card) -> dict | None:
    """Extraire les données d'une carte d'annonce Centris."""
    try:
        price_el = card.find(class_=re.compile(r"price"))
        if not price_el:
            return None
        price = _to_int(price_el.get_text())
        if not price:
            return None

        addr_el = card.find(class_=re.compile(r"address|location|civic"))
        address = addr_el.get_text(strip=True) if addr_el else "N/A"

        link_el = card.find("a", href=True)
        href    = link_el["href"] if link_el else ""
        url     = (BASE_URL + href) if href.startswith("/") else href

        img_el = card.find("img")
        image  = img_el.get("src", "") or img_el.get("data-src", "") if img_el else ""

        full_text = card.get_text(" ", strip=True)
        units     = _extract_units(full_text) or 2

        # Revenus bruts déclarés (si disponibles dans la fiche)
        income = _extract_income(full_text)

        return {
            "id":            "ct_" + hashlib.md5(url.encode()).hexdigest()[:10],
            "source":        "Centris",
            "type":          _detect_type(units),
            "units":         units,
            "price":         price,
            "address":       address,
            "url":           url,
            "image":         image,
            "description":   full_text[:500],
            "declared_income": income,  # None si non déclaré
            "scraped_at":    datetime.now().isoformat(),
        }
    except Exception:
        return None


def _detect_type(units: int) -> str:
    return {2: "Duplex", 3: "Triplex", 4: "Quadruplex", 5: "Quintuplex"}.get(units, f"{units}-plex")


def _to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _extract_units(text: str) -> int | None:
    t = text.lower()
    if "quintuplex" in t: return 5
    if "quadruplex" in t: return 4
    if "triplex"    in t: return 3
    if "duplex"     in t: return 2
    m = re.search(r"(\d+)\s*(?:logements?|appartements?|units?|portes?)", t)
    return int(m.group(1)) if m else None


def _extract_income(text: str) -> int | None:
    """Tenter d'extraire les revenus bruts déclarés dans l'annonce."""
    m = re.search(r"revenus?\s*(?:bruts?)?\s*:?\s*\$?\s*([\d\s,]+)", text, re.IGNORECASE)
    if m:
        return _to_int(m.group(1))
    return None


if __name__ == "__main__":
    print("Scraping Centris — plex Montréal...")
    print()

    listings = scrape_centris(max_price=2_000_000)

    if not listings:
        print("Aucune annonce trouvée. L'API Centris a peut-être changé.")
    else:
        output = "../../data/listings.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(listings, f, ensure_ascii=False, indent=2)

        print()
        print(f"{'='*50}")
        print(f"TOTAL : {len(listings)} plex")
        print(f"{'='*50}")

        by_type: dict[str, int] = {}
        for l in listings:
            t = l["type"]
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        prices = [l["price"] for l in listings]
        print()
        print(f"Prix min  : ${min(prices):,}")
        print(f"Prix max  : ${max(prices):,}")
        print(f"Prix moyen: ${int(sum(prices)/len(prices)):,}")
        print()
        print(f"Sauvegardé dans : {output}")
