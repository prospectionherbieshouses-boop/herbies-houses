"""
terrains.py — Scrape les terrains résidentiels à potentiel de développement multilogement.

Critères :
    - Zonage résidentiel
    - Prix par logement estimé < 40 000 $
    - Estimation : 1 logement par 200 m² de terrain (norme urbaine Québec)

Villes : Montréal, Verdun, Cowansville, Magog, Bromont, Trois-Rivières

Usage :
    python terrains.py
"""

import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

BASE_URL   = "https://www.centris.ca"
PRICE_PER_UNIT_MAX = 40_000   # seuil : < 40 000 $ par logement potentiel
M2_PER_UNIT        = 200      # 1 logement par 200 m² (conservateur)

SEARCH_CITIES = [
    ("Montréal",       "montreal"),
    ("Verdun",         "verdun"),
    ("Cowansville",    "cowansville"),
    ("Magog",          "magog"),
    ("Bromont",        "bromont"),
    ("Trois-Rivières", "trois-rivieres"),
]


def scrape_terrains() -> list[dict]:
    """Scrape tous les terrains résidentiels dans les villes cibles."""
    all_terrains = []
    seen_ids     = set()

    for city_name, city_slug in SEARCH_CITIES:
        search_url = f"{BASE_URL}/fr/terrain-residentiels~a-vendre~{city_slug}?view=Thumbnail"
        print(f"\n  Ville : {city_name}")

        try:
            from playwright.sync_api import sync_playwright
            terrains = _scrape_playwright(search_url, city_name)
        except ImportError:
            terrains = _scrape_requests(search_url, city_name)

        new = [t for t in terrains if t["id"] not in seen_ids]
        for t in new:
            seen_ids.add(t["id"])
        all_terrains.extend(new)
        print(f"  {city_name} : {len(new)} terrains")

    return all_terrains


def _scrape_playwright(search_url: str, city_name: str) -> list[dict]:
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    terrains = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx  = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-CA", viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page.goto(search_url, wait_until="networkidle", timeout=60_000)
        time.sleep(3)

        try:
            page.click("button:has-text('Accepter')", timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        page_num = 1
        while True:
            html  = page.content()
            soup  = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item"))

            if not cards:
                break

            for card in cards:
                t = _parse_terrain_card(card, city_name)
                if t:
                    terrains.append(t)

            print(f"    Page {page_num} : {len(cards)} terrains")

            try:
                next_btn = page.query_selector("li.next a, a[aria-label='Suivant']")
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15_000)
                time.sleep(3)
                page_num += 1
            except Exception:
                break

        browser.close()

    return terrains


def _scrape_requests(search_url: str, city_name: str) -> list[dict]:
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    })

    terrains = []
    page_num  = 1

    while True:
        url = search_url if page_num == 1 else f"{search_url}&page={page_num}"
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"    Erreur page {page_num}: {e}")
            break

        from bs4 import BeautifulSoup
        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"property-thumbnail-item"))

        if not cards:
            break

        for card in cards:
            t = _parse_terrain_card(card, city_name)
            if t:
                terrains.append(t)

        print(f"    Page {page_num} : {len(cards)} terrains")

        if len(cards) < 20:
            break

        page_num += 1
        time.sleep(3)

    return terrains


def _parse_terrain_card(card, city_name: str) -> dict | None:
    """Extraire les données d'une carte de terrain."""
    try:
        # Prix
        price_el = card.find(class_=re.compile(r"price"))
        if not price_el:
            return None
        price = _to_int(price_el.get_text())
        if not price or price < 10_000:
            return None

        # Adresse
        addr_el = card.find(class_=re.compile(r"address|location|civic"))
        address = addr_el.get_text(strip=True) if addr_el else city_name

        # Lien
        link_el = card.find("a", href=True)
        href    = link_el["href"] if link_el else ""
        url     = (BASE_URL + href) if href.startswith("/") else href

        # Photo
        img_el = card.find("img")
        image  = ""
        if img_el:
            image = img_el.get("src","") or img_el.get("data-src","") or img_el.get("data-lazy-src","")

        # Texte complet — extraire dimensions et superficie
        full_text = card.get_text(" ", strip=True)
        area_m2   = _extract_area(full_text)
        dims      = _extract_dims(full_text)

        # Estimation du nombre de logements potentiels
        potential_units = max(1, int(area_m2 // M2_PER_UNIT)) if area_m2 else None
        price_per_unit  = round(price / potential_units) if potential_units else None

        # Filtrer : prix/logement > seuil → pas intéressant
        if price_per_unit and price_per_unit > PRICE_PER_UNIT_MAX:
            return None

        return {
            "id":              "tr_" + hashlib.md5(url.encode()).hexdigest()[:10],
            "source":          "Centris",
            "type":            "Terrain résidentiel",
            "city":            city_name,
            "price":           price,
            "address":         address,
            "url":             url,
            "image":           image,
            "area_m2":         area_m2,
            "dimensions":      dims,
            "potential_units": potential_units,
            "price_per_unit":  price_per_unit,
            "description":     full_text[:400],
            "scraped_at":      datetime.now().isoformat(),
        }
    except Exception:
        return None


def _extract_area(text: str) -> float | None:
    """Extraire la superficie en m²."""
    t = text.lower()
    # "1 200 m²" ou "1200m2" ou "0,12 ha"
    m = re.search(r"([\d\s,.]+)\s*m\s*[²2]", t)
    if m:
        val = _to_float(m.group(1))
        if val and 50 < val < 50_000:
            return val
    # Hectares → m²
    m = re.search(r"([\d,.]+)\s*ha", t)
    if m:
        val = _to_float(m.group(1))
        if val:
            return round(val * 10_000, 1)
    # "30 x 40" → calculer
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        a, b = _to_float(m.group(1)), _to_float(m.group(2))
        if a and b:
            return round(a * b, 1)
    return None


def _extract_dims(text: str) -> str | None:
    """Extraire les dimensions (ex. '30 x 45 pi')."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(pi|ft|m|mèt)?", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} × {m.group(2)} {m.group(3) or ''}".strip()
    return None


def _to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _to_float(text: str) -> float | None:
    try:
        return float(re.sub(r"[^\d.]", "", text.replace(",", ".")))
    except Exception:
        return None


if __name__ == "__main__":
    print("Scraping terrains résidentiels...")
    print()

    terrains = scrape_terrains()

    if not terrains:
        print("Aucun terrain trouvé répondant aux critères.")
    else:
        out = Path(__file__).parent.parent / "app" / "terrains.json"
        payload = {
            "scraped_at": datetime.now().isoformat(),
            "count":      len(terrains),
            "terrains":   terrains,
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"\nTOTAL : {len(terrains)} terrains < {PRICE_PER_UNIT_MAX:,}$/log. potentiel")
        print(f"Sauvegardé : {out}")
        print()

        top = sorted(terrains, key=lambda x: x.get("price_per_unit") or 999_999)[:5]
        print("Top 5 (prix/logement le plus bas) :")
        for i, t in enumerate(top, 1):
            ppu = t.get("price_per_unit")
            u   = t.get("potential_units")
            print(f"  {i}. {t['address']} — ${t['price']:,} — {u} log. potentiels — {f'${ppu:,}/log.' if ppu else 'N/A'}")
