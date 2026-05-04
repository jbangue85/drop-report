from app.parser import parse_meta_csv

with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    content = f.read()

records = parse_meta_csv(content, "test.csv")
print(f"Parsed {len(records)} records")
if records:
    print(records[0])
