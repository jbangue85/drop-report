import sys
import types
sys.modules['openpyxl'] = types.ModuleType('openpyxl')

from app.parser import parse_meta_csv
with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    records = parse_meta_csv(f.read(), "test.csv")
print("Found records:", len(records))
if records:
    print("First record:", records[0])
