"""
centris.py — Scrape les plex à vendre sur Centris via Playwright.

Navigue directement sur la page de recherche Centris et extrait les annonces.

Usage :
    python centris.py
"""

import re
import json
import time
import hashlib
from datetime import datetime

BASE_URL  = "https://www.centris.ca"
PAGE_SIZE = 20

# Villes cibles — slug Centris dans l'URL
SEARCH_CITIES = [
    ("Montréal",      "montreal"),
    ("Verdun",        "verdun"),
    ("Cowansville",   "cowansville"),
    ("Magog",         "magog"),
    ("Bromont",       "bromont"),
    ("Trois-Rivières","trois-rivieres"),
]


def scrape_centris(max_price: int = 2_000_000) -> list[dict]:
    """Scrape les plex à vendre dans toutes les villes cibles."""
    all_listings = []
    seen_ids     = set()

    for city_name, city_slug in SEARCH_CITIES:
        search_url = f"{BASE_URL}/fr/plex~a-vendre~{city_slug}?view=Thumbnail"
        print(f"\n  Ville : {city_name}")
        try:
            from playwright.sync_api import sync_playwright
            listings = _scrape_playwright(max_price, search_url)
        except ImportError:
            listings = _scrape_requests(max_price, search_url)

        new = [l for l in listings if l["id"] not in seen_ids]
        for l in new:
            seen_ids.add(l["id"])
        all_listings.extend(new)
        print(f"  {city_name} : {len(new)} annonces")

    return all_listings


def _scrape_playwright(max_price: int, search_url: str = "") -> list[dict]:
    """Scrape via Playwright (navigateur réel, contourne le bot-detection)."""
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    listings = []
    seen_ids  = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-CA",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"  Ouverture de Centris...")
        page.goto(search_url, wait_until="networkidle", timeout=60_000)
        time.sleep(3)

        # Fermer popup cookie si présent
        try:
            page.click("button:has-text('Accepter')", timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        page_num = 1
        while True:
            print(f"  Page {page_num}...")
            html  = page.content()
            soup  = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item"))

            if not cards:
                cards = soup.find_all("article", class_=re.compile(r"property|listing"))

            if not cards:
                print(f"  Aucune carte trouvée sur la page {page_num}")
                break

            for card in cards:
                listing = _parse_card(card)
                if not listing:
                    continue
                if listing["id"] in seen_ids:
                    continue
                if listing["price"] > max_price:
                    continue
                listings.append(listing)
                seen_ids.add(listing["id"])

            print(f"  Page {page_num} : {len(cards)} annonces | total : {len(listings)}")

            # Chercher le bouton "Page suivante"
            try:
                next_btn = page.query_selector("li.next a, a[aria-label='Suivant'], button:has-text('Suivant')")
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15_000)
                time.sleep(3)
                page_num += 1
            except Exception:
                break

        browser.close()

    return listings


def _fetch_declared_income(url: str, session) -> int | None:
    """Visite la page d'annonce et extrait les revenus bruts déclarés."""
    try:
        from bs4 import BeautifulSoup
        time.sleep(2)  # délai anti-scraping
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        # Chercher "Revenu(s) brut(s)" dans les tableaux de données
        for el in soup.find_all(string=re.compile(r"revenu.{0,10}brut", re.IGNORECASE)):
            parent = el.find_parent()
            if not parent:
                continue
            # Chercher la valeur dans les éléments voisins
            sibling = parent.find_next_sibling()
            if sibling:
                val = _to_int(sibling.get_text())
                if val and 1_000 < val < 500_000:
                    # Centris affiche souvent en annuel, convertir en mensuel
                    return val // 12 if val > 20_000 else val
            # Parfois dans le même élément
            val = _to_int(parent.get_text())
            if val and 1_000 < val < 500_000:
                return val // 12 if val > 20_000 else val
    except Exception:
        pass
    return None


def _scrape_requests(max_price: int, search_url: str = "") -> list[dict]:
    """Fallback : scrape via requests + BeautifulSoup."""
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
        "Referer": BASE_URL + "/fr",
    })

    listings = []
    seen_ids  = set()
    page_num  = 1

    while True:
        url = search_url if page_num == 1 else f"{search_url}&page={page_num}"
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Erreur page {page_num}: {e}")
            break

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item"))

        if not cards:
            break

        for card in cards:
            listing = _parse_card(card)
            if not listing or listing["id"] in seen_ids or listing["price"] > max_price:
                continue

            # Visiter la page d'annonce pour obtenir les vrais revenus déclarés
            if listing.get("url") and not listing.get("declared_income"):
                income = _fetch_declared_income(listing["url"], session)
                if income:
                    listing["declared_income"] = income
                    print(f"    Revenus déclarés : {listing['address']} → {income:,}$/mois")

            listings.append(listing)
            seen_ids.add(listing["id"])

        print(f"  Page {page_num} : {len(cards)} annonces | total : {len(listings)}")

        if len(cards) < PAGE_SIZE:
            break

        page_num += 1
        time.sleep(3)

    return listings


def _parse_card(card) -> dict | None:
    """Extraire les données d'une carte d'annonce Centris."""
    try:
        # Prix
        price_el = card.find(class_=re.compile(r"price"))
        if not price_el:
            return None
        price = _to_int(price_el.get_text())
        if not price:
            return None

        # Adresse
        addr_el = card.find(class_=re.compile(r"address|location|civic"))
        address = addr_el.get_text(strip=True) if addr_el else "N/A"

        # Lien
        link_el = card.find("a", href=True)
        href    = link_el["href"] if link_el else ""
        url     = (BASE_URL + href) if href.startswith("/") else href

        # Photo
        img_el = card.find("img")
        image  = ""
        if img_el:
            image = img_el.get("src", "") or img_el.get("data-src", "") or img_el.get("data-lazy-src", "")

        # Texte complet
        full_text = card.get_text(" ", strip=True)
        units     = _extract_units(full_text) or 2
        income    = _extract_income(full_text)

        return {
            "id":              "ct_" + hashlib.md5(url.encode()).hexdigest()[:10],
            "source":          "Centris",
            "type":            _detect_type(units),
            "units":           units,
            "price":           price,
            "address":         address,
            "url":             url,
            "image":           image,
            "description":     full_text[:500],
            "declared_income": income,
            "scraped_at":      datetime.now().isoformat(),
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
    m = re.search(r"revenus?\s*(?:bruts?)?\s*:?\s*\$?\s*([\d\s,]+)", text, re.IGNORECASE)
    return _to_int(m.group(1)) if m else None


if __name__ == "__main__":
    print("Scraping Centris — plex Montréal...")
    print()

    listings = scrape_centris(max_price=2_000_000)

    if not listings:
        print("Aucune annonce trouvée.")
    else:
        with open("listings_centris.json", "w", encoding="utf-8") as f:
            json.dump(listings, f, ensure_ascii=False, indent=2)
        print(f"\nTOTAL : {len(listings)} annonces — sauvegardé dans listings_centris.json")
