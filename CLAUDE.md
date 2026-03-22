# Herbies — Prospection Immobilière Montréal

## C'est quoi ce projet ?
Application de prospection immobilière pour trouver des plex et multilogements
à cashflow positif à Montréal. L'app scrape Centris automatiquement, analyse
la rentabilité de chaque propriété avec les taux hypothécaires actuels, et
présente les meilleurs deals.

## Structure du projet
```
herbies-houses/
├── app/                    # PWA mobile (frontend)
│   ├── index.html          # Application principale (3 onglets)
│   ├── manifest.json       # Config installation mobile
│   ├── sw.js               # Service worker (mode offline)
│   └── icon-192.svg        # Icône app
│
├── backend/                # Serveur API Python
│   ├── main.py             # FastAPI — routes /chat /scrape /analyze
│   ├── analyzer.py         # Calculs cashflow et rentabilité
│   ├── notifier.py         # Alertes email/SMS deals
│   └── requirements.txt
│
├── scraper/                # Scraping Centris
│   ├── scraper.py          # Playwright + stealth anti-détection
│   └── centris.py          # Sélecteurs CSS et parsing
│
├── data/                   # Données persistantes
│   ├── listings.json       # Annonces scrapées
│   └── listings_cache.json # Cache pour éviter re-scraping
│
└── CLAUDE.md               # Ce fichier
```

## Stack technique
- **Frontend** : HTML/CSS/JS vanilla — PWA installable sur iPhone/Android
- **Backend** : Python 3.11+ avec FastAPI
- **Scraper** : Playwright (Chromium headless) avec stealth
- **Déploiement** : GitHub Pages (front) + Railway (back)

## Variables financières (mars 2026)
- Taux directeur BdC : **2,25 %**
- Taux préférentiel : **4,45 %**
- Taux fixe 5 ans utilisé : **4,69 %**
- Taux variable estimé : **3,95 %**
- Mise de fonds par défaut : **20 %**
- Amortissement par défaut : **25 ans**
- Taux de vacance par défaut : **3 %**

## Formule cashflow utilisée
```
Cashflow = Revenus bruts
         - Perte vacance (3%)
         - Paiement hypothèque mensuel
         - Taxes municipales (0,8% prix / 12)
         - Assurances (2 400$ / 12)
         - Entretien (1% prix / 12)
```

## Critères d'un bon deal
- Cashflow mensuel > **200 $/mois** minimum
- Cap rate > **4,5 %** (idéalement 5 %+)
- MRB (multiplicateur revenus bruts) < **15x**

## Cibles de scraping
- **Centris.ca** — plex à vendre Montréal
- Quartiers prioritaires : Rosemont, Villeray, Ahuntsic, Montréal-Nord, St-Michel

## Ce qu'il reste à faire
- [ ] Connecter le bouton "Lancer scraper" dans l'app au vrai scraper Python
- [ ] Créer la route FastAPI `/scrape` qui appelle scraper.py
- [ ] Créer la route FastAPI `/analyze` qui retourne le cashflow calculé
- [ ] Déployer le backend sur Railway
- [ ] Activer GitHub Pages pour le frontend

## Comment lancer en local
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Scraper (manuel)
cd scraper
pip install playwright
playwright install chromium
python scraper.py

# Frontend — ouvrir simplement dans le navigateur
open app/index.html
```

## Notes importantes pour Claude Code
- Ne jamais hardcoder de clés API dans le code — utiliser le fichier .env
- Le fichier .env contient : ANTHROPIC_API_KEY, EMAIL_SMTP, etc.
- Toujours respecter les délais anti-scraping (min 3s entre requêtes)
- Les fichiers .pyc et __pycache__ ne doivent pas être commités (voir .gitignore)
- Langue du code : commentaires en français, variables en anglais
