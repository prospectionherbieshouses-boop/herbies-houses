"""
notifier.py — Alertes email pour les bons deals.

Envoie un email récapitulatif quand de nouveaux deals > seuil sont détectés.
Configure les variables dans .env :
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_USER, EMAIL_SMTP_PASS, EMAIL_TO
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def _smtp_config() -> dict:
    return {
        "host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
        "user": os.getenv("EMAIL_SMTP_USER", ""),
        "password": os.getenv("EMAIL_SMTP_PASS", ""),
        "to": os.getenv("EMAIL_TO", ""),
    }


def send_deal_alert(deals: list[dict], min_cashflow: int = 200) -> bool:
    """
    Envoie un email avec les meilleurs deals.
    Retourne True si envoi réussi, False sinon.
    """
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["to"]:
        print("[Notifier] Variables EMAIL_* non configurées — email non envoyé")
        return False

    bons_deals = [d for d in deals if d.get("cashflow_monthly", 0) >= min_cashflow]
    if not bons_deals:
        print("[Notifier] Aucun deal à notifier")
        return False

    subject = f"Herbies — {len(bons_deals)} nouveau(x) deal(s) immobilier(s) 🏠"
    html    = _build_email_html(bons_deals)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["user"]
    msg["To"]      = cfg["to"]
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], cfg["to"], msg.as_string())
        print(f"[Notifier] Email envoyé à {cfg['to']} — {len(bons_deals)} deals")
        return True
    except Exception as e:
        print(f"[Notifier] Erreur envoi email : {e}")
        return False


def _build_email_html(deals: list[dict]) -> str:
    """Construire le corps HTML de l'email."""
    rows = ""
    for d in deals[:10]:  # max 10 deals par email
        cashflow = d.get("cashflow_monthly", 0)
        cap_rate = d.get("cap_rate_pct", 0)
        mrb      = d.get("mrb", 0)
        color    = "#22c55e" if cashflow >= 400 else "#f59e0b" if cashflow >= 200 else "#ef4444"

        rows += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid #f0f0f0">
                <strong>{d.get('type','?')} — {d.get('address','N/A')}</strong><br>
                <small style="color:#666">{d.get('source','Centris')}</small>
            </td>
            <td style="padding:12px;border-bottom:1px solid #f0f0f0;text-align:right">
                ${d.get('price',0):,}
            </td>
            <td style="padding:12px;border-bottom:1px solid #f0f0f0;text-align:right;color:{color};font-weight:bold">
                {'+' if cashflow >= 0 else ''}{cashflow:,.0f} $/mois
            </td>
            <td style="padding:12px;border-bottom:1px solid #f0f0f0;text-align:right">
                {cap_rate:.1f}% | MRB {mrb:.1f}x
            </td>
            <td style="padding:12px;border-bottom:1px solid #f0f0f0">
                <a href="{d.get('url','#')}" style="color:#6366f1">Voir →</a>
            </td>
        </tr>"""

    date_str = datetime.now().strftime("%d %B %Y à %H:%M")
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:sans-serif;max-width:800px;margin:auto;padding:20px;color:#1a1a1a">
        <h1 style="color:#6366f1">🏠 Herbies — Nouvelles opportunités</h1>
        <p style="color:#666">{date_str}</p>
        <p>{len(deals)} deal(s) avec cashflow positif détecté(s) sur Centris :</p>

        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
            <thead>
                <tr style="background:#6366f1;color:white">
                    <th style="padding:12px;text-align:left">Propriété</th>
                    <th style="padding:12px;text-align:right">Prix</th>
                    <th style="padding:12px;text-align:right">Cashflow</th>
                    <th style="padding:12px;text-align:right">Cap rate | MRB</th>
                    <th style="padding:12px">Lien</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <p style="margin-top:24px;color:#999;font-size:12px">
            Calculs basés sur : taux fixe 4,69 % · mise de fonds 20 % · amort. 25 ans · vacance 3 %
        </p>
        <p style="color:#999;font-size:12px">— Herbies Houses</p>
    </body>
    </html>"""
