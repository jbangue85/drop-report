import asyncio
from app.database import get_db

with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    content = f.read()

conn = get_db()
from app.parser import parse_meta_csv, upsert_meta_spend

records = parse_meta_csv(content, "test.csv")
print("Parsed Meta CSV records:", len(records))
if len(records) > 0:
    count = upsert_meta_spend(conn, records)
    print("Upserted:", count)
else:
    print("NO RECORDS")

