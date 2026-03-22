"""
scraper.py — Scraping Centris avec Playwright (Chromium headless + stealth).

Utilise Playwright pour contourner la détection bot de Centris.
Fallback sur requests si Playwright n'est pas installé.

Usage :
    python scraper.py
"""

import json
import time
import sys
import os

# Ajouter le dossier parent au path pour accéder à data/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(DATA_DIR, "listings_cache.json")
OUT_FILE   = os.path.join(DATA_DIR, "listings.json")


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def run_with_playwright(max_price: int = 2_000_000) -> list[dict]:
    """Scrape Centris via Playwright (stealth headless Chromium)."""
    from playwright.sync_api import sync_playwright
    import re, hashlib
    from datetime import datetime
    from bs4 import BeautifulSoup

    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-CA",
            viewport={"width": 1280, "height": 800},
        )

        # Masquer les traces Playwright
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        page = context.new_page()

        print("  Chargement de Centris...")
        page.goto("https://www.centris.ca/fr/plex~a-vendre~montreal", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Fermer popup cookies si présent
        try:
            page.click("button[id*='cookie'], button[class*='cookie'], #onetrust-accept-btn-handler", timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        page_num = 1
        while True:
            print(f"  Page {page_num}...")
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item"))
            if not cards:
                cards = soup.find_all("article", class_=re.compile(r"property"))
            if not cards:
                break

            for card in cards:
                # Prix
                price_el = card.find(class_=re.compile(r"price"))
                if not price_el:
                    continue
                price_text = re.sub(r"[^\d]", "", price_el.get_text())
                if not price_text:
                    continue
                price = int(price_text)
                if price > max_price:
                    continue

                # Adresse
                addr_el = card.find(class_=re.compile(r"address|location|civic"))
                address = addr_el.get_text(strip=True) if addr_el else "N/A"

                # URL
                link_el = card.find("a", href=True)
                href    = link_el["href"] if link_el else ""
                url     = ("https://www.centris.ca" + href) if href.startswith("/") else href

                # Image
                img_el = card.find("img")
                image  = (img_el.get("src", "") or img_el.get("data-src", "")) if img_el else ""

                # Type / logements
                full_text = card.get_text(" ", strip=True)
                units     = _extract_units(full_text) or 2

                listings.append({
                    "id":          "ct_" + hashlib.md5(url.encode()).hexdigest()[:10],
                    "source":      "Centris",
                    "type":        _detect_type(units),
                    "units":       units,
                    "price":       price,
                    "address":     address,
                    "url":         url,
                    "image":       image,
                    "description": full_text[:500],
                    "scraped_at":  datetime.now().isoformat(),
                })

            # Pagination — chercher le bouton "Suivant"
            try:
                next_btn = page.query_selector("a[aria-label*='suivant'], a[rel='next'], .next-page")
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(3)
                page_num += 1
            except Exception:
                break

        browser.close()

    return listings


def run_with_requests(max_price: int = 2_000_000) -> list[dict]:
    """Fallback : scrape via requests + BeautifulSoup (sans Playwright)."""
    from centris import scrape_centris
    return scrape_centris(max_price=max_price)


def _detect_type(units: int) -> str:
    return {2: "Duplex", 3: "Triplex", 4: "Quadruplex", 5: "Quintuplex"}.get(units, f"{units}-plex")


def _extract_units(text: str) -> int | None:
    import re
    t = text.lower()
    if "quintuplex" in t: return 5
    if "quadruplex" in t: return 4
    if "triplex"    in t: return 3
    if "duplex"     in t: return 2
    m = re.search(r"(\d+)\s*(?:logements?|appartements?|units?|portes?)", t)
    return int(m.group(1)) if m else None


def run(max_price: int = 2_000_000) -> list[dict]:
    """Point d'entrée principal — essaie Playwright, fallback sur requests."""
    cache = load_cache()

    print("Démarrage du scraping Centris...")
    try:
        listings = run_with_playwright(max_price=max_price)
        method   = "Playwright"
    except ImportError:
        print("  Playwright non installé — fallback sur requests")
        listings = run_with_requests(max_price=max_price)
        method   = "requests"
    except Exception as e:
        print(f"  Playwright échoué ({e}) — fallback sur requests")
        listings = run_with_requests(max_price=max_price)
        method   = "requests"

    # Dédupliquer avec le cache
    new_listings = []
    for l in listings:
        if l["id"] not in cache:
            new_listings.append(l)
            cache[l["id"]] = l["scraped_at"]

    print(f"  Méthode : {method}")
    print(f"  Nouvelles annonces : {len(new_listings)} / {len(listings)} trouvées")

    # Sauvegarder
    save_cache(cache)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)

    return listings


if __name__ == "__main__":
    listings = run(max_price=2_000_000)
    print(f"\nTotal : {len(listings)} plex sauvegardés dans data/listings.json")
