import sqlite3
import re
import unicodedata

def normalize(s):
    if not s: return ""
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode("utf-8")
    s = s.lower()
    return re.sub(r'[^a-z0-9]', ' ', s)

conn = sqlite3.connect("data/dropreport.db")
products = [r[0] for r in conn.execute("SELECT DISTINCT producto FROM orders WHERE producto IS NOT NULL").fetchall()]

campaigns = [
    "Limpiador Eléctrico Biberones — 21 ABR",
    "KIT-DE-LIMPIEZA-PARA-BIBERONES - 26-04-2026",
    "Armadura Dental - Sensibilidad",
    "Armadura Dental",
    "Quitaoxido Addio 1 Litro",
    "BASE EN BARRA 2 EN 1",
    "CleanDriver"
]

for c in campaigns:
    nc = set(normalize(c).split())
    best_p = None
    best_score = 0
    for p in products:
        np = set(normalize(p).split())
        score = len(nc.intersection(np))
        if score > best_score:
            best_score = score
            best_p = p
    print(f"Campaña: {c} -> Producto: {best_p} (score: {best_score})")

