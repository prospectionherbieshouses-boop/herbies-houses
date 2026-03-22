"""
analyzer.py — Calculs financiers pour l'investissement immobilier.

Formule cashflow (mars 2026) :
    Cashflow = Revenus bruts
             - Perte vacance (3%)
             - Paiement hypothèque mensuel
             - Taxes municipales (0,8% prix / 12)
             - Assurances (2 400$ / 12)
             - Entretien (1% prix / 12)

Critères d'un bon deal :
    - Cashflow > 200 $/mois
    - Cap rate > 4,5 %
    - MRB < 15x
"""

# ── Taux par défaut (mars 2026) ──────────────────────────────────────────────
RATE_FIXED    = 0.0469   # taux fixe 5 ans
RATE_VARIABLE = 0.0395   # taux variable estimé
DOWN_PCT      = 0.20     # mise de fonds 20%
AMORT_YEARS   = 25
VACANCY_RATE  = 0.03     # 3% taux de vacance
INSURANCE_YR  = 2_400    # assurances annuelles (fixe)
TAX_RATE      = 0.008    # taxes municipales 0,8% du prix
MAINT_RATE    = 0.01     # entretien 1% du prix / an

# Loyers estimés par unité (Montréal, 2026)
RENT_PREMIUM  = 1_600    # Outremont, Westmount, Plateau, Mile-End
RENT_CORE     = 1_250    # Rosemont, Villeray, Ahuntsic, Côte-des-Neiges
RENT_STANDARD = 1_000    # Montréal-Nord, St-Michel, Anjou, Montréal-Est
RENT_DEFAULT  = 1_100    # défaut si quartier inconnu

PREMIUM_HOODS  = ["outremont", "westmount", "plateau", "mile-end", "mont-royal"]
CORE_HOODS     = ["rosemont", "villeray", "ahuntsic", "côte-des-neiges", "cote-des-neiges",
                  "hochelaga", "maisonneuve", "verdun", "lasalle", "saint-laurent"]
STANDARD_HOODS = ["montréal-nord", "montreal-nord", "st-michel", "saint-michel",
                  "anjou", "montréal-est", "montreal-est", "rivière-des-prairies"]


# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def estimate_rent_per_unit(address: str) -> int:
    """Loyer estimé par unité selon le quartier."""
    addr = address.lower()
    if any(h in addr for h in PREMIUM_HOODS):
        return RENT_PREMIUM
    if any(h in addr for h in CORE_HOODS):
        return RENT_CORE
    if any(h in addr for h in STANDARD_HOODS):
        return RENT_STANDARD
    return RENT_DEFAULT


def calculate_mortgage(price: int, down_pct: float = DOWN_PCT,
                        rate: float = RATE_FIXED, years: int = AMORT_YEARS) -> float:
    """Paiement hypothécaire mensuel (capital + intérêts)."""
    principal    = price * (1 - down_pct)
    monthly_rate = rate / 12
    n            = years * 12
    payment      = principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    return round(payment, 2)


def calculate_cashflow(
    price: int,
    units: int,
    address: str = "",
    declared_income: int | None = None,
    down_pct: float = DOWN_PCT,
    rate: float = RATE_FIXED,
    years: int = AMORT_YEARS,
) -> dict:
    """
    Calcul complet du cashflow mensuel.
    Si declared_income est fourni (revenus bruts déclarés par le vendeur), l'utilise.
    Sinon, estime les revenus selon le quartier.
    """
    # Revenus bruts mensuels
    rent_per_unit   = estimate_rent_per_unit(address)
    estimated_rent  = units * rent_per_unit
    gross_rent      = declared_income if declared_income else estimated_rent

    # Dépenses mensuelles
    vacancy         = round(gross_rent * VACANCY_RATE, 2)
    net_rent        = gross_rent - vacancy
    mortgage        = calculate_mortgage(price, down_pct, rate, years)
    taxes           = round(price * TAX_RATE / 12, 2)
    insurance       = round(INSURANCE_YR / 12, 2)
    maintenance     = round(price * MAINT_RATE / 12, 2)

    total_expenses  = round(mortgage + taxes + insurance + maintenance, 2)
    cashflow        = round(net_rent - total_expenses, 2)

    # Métriques d'investissement
    noi_annual      = round((net_rent - taxes - insurance - maintenance) * 12, 2)
    cap_rate        = round(noi_annual / price * 100, 2) if price else 0
    mrb             = round(price / (gross_rent * 12), 2) if gross_rent else 0
    gross_yield     = round((gross_rent * 12) / price * 100, 2) if price else 0
    mise_de_fonds   = round(price * down_pct)

    return {
        # Revenus
        "gross_rent_monthly":    gross_rent,
        "estimated_rent":        estimated_rent,
        "rent_per_unit":         rent_per_unit,
        "income_declared":       declared_income is not None,

        # Dépenses
        "vacancy_monthly":       vacancy,
        "mortgage_monthly":      mortgage,
        "taxes_monthly":         taxes,
        "insurance_monthly":     insurance,
        "maintenance_monthly":   maintenance,
        "total_expenses_monthly": total_expenses,

        # Résultat
        "cashflow_monthly":      cashflow,
        "cashflow_annual":       round(cashflow * 12, 2),
        "mise_de_fonds":         mise_de_fonds,

        # Métriques
        "cap_rate_pct":          cap_rate,
        "mrb":                   mrb,
        "gross_yield_pct":       gross_yield,

        # Évaluation du deal
        "is_good_deal":          cashflow >= 200 and cap_rate >= 4.5 and mrb <= 15,
        "cashflow_ok":           cashflow >= 200,
        "cap_rate_ok":           cap_rate >= 4.5,
        "mrb_ok":                mrb <= 15,

        # Paramètres utilisés
        "rate_used":             rate,
        "down_pct_used":         down_pct,
        "amort_years":           years,
    }


def score_deal(financials: dict) -> int:
    """Score simple de 1 à 10 basé sur les métriques financières."""
    score = 5

    # Cashflow
    cf = financials["cashflow_monthly"]
    if cf >= 600:   score += 3
    elif cf >= 400: score += 2
    elif cf >= 200: score += 1
    elif cf < 0:    score -= 3
    elif cf < 100:  score -= 1

    # Cap rate
    cr = financials["cap_rate_pct"]
    if cr >= 6.0:   score += 2
    elif cr >= 5.0: score += 1
    elif cr < 4.0:  score -= 1

    # MRB
    mrb = financials["mrb"]
    if mrb <= 12:   score += 1
    elif mrb >= 18: score -= 1

    return max(1, min(10, score))


def analyze_listing(listing: dict) -> dict:
    """Analyser une annonce et retourner les métriques financières + score."""
    financials = calculate_cashflow(
        price           = listing["price"],
        units           = listing.get("units", 2),
        address         = listing.get("address", ""),
        declared_income = listing.get("declared_income"),
    )
    score = score_deal(financials)
    return {**financials, "score": score}


def analyze_all(listings: list[dict]) -> list[dict]:
    """Analyser les annonces avec revenus déclarés seulement, triées par score."""
    results = []
    discarded = 0
    for listing in listings:
        if not listing.get("declared_income"):
            discarded += 1
            continue
        analysis = analyze_listing(listing)
        results.append({**listing, **analysis})
    if discarded:
        print(f"  {discarded} annonces sans revenus déclarés — ignorées")
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
