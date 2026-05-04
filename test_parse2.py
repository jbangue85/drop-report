import csv, io
with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    text = f.read().decode("utf-8", errors="replace")
reader = csv.DictReader(io.StringIO(text))
campaigns = set()
for r in reader:
    if "Nombre de la campaña" in r:
        campaigns.add(r["Nombre de la campaña"])
for c in campaigns:
    print(c)
