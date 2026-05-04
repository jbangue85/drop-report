import csv
import io

def parse_meta_csv(file_bytes: bytes, filename: str):
    text = file_bytes.decode('utf-8-sig', errors='replace') # using utf-8-sig to remove BOM
    reader = csv.DictReader(io.StringIO(text))
    
    records = []
    for row in reader:
        if "Inicio del informe" not in row:
            print("Missing Inicio del informe. Keys:", list(row.keys()))
            break
        print("Found it!")
        break

with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    content = f.read()

parse_meta_csv(content, "test.csv")
