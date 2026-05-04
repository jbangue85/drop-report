import csv
import io

def parse_meta_csv(file_bytes: bytes, filename: str):
    text = file_bytes.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    
    records = []
    for row in reader:
        if "Inicio del informe" not in row or "Importe gastado (COP)" not in row:
            continue
            
        fecha = row.get("Inicio del informe", "").strip()
        campaign = row.get("Nombre de la campaña", "").strip()
        spend_str = row.get("Importe gastado (COP)", "0").strip()
        results_str = row.get("Resultados", "0").strip()
        
        if not fecha or not campaign:
            continue
            
        try:
            spend = float(spend_str) if spend_str else 0.0
        except ValueError:
            spend = 0.0
            
        try:
            results = int(results_str) if results_str else 0
        except ValueError:
            results = 0
            
        if spend > 0 or results > 0:
            records.append({
                "fecha": fecha,
                "campaign_name": campaign,
                "spend": spend,
                "results": results
            })
            
    return records

with open("Mercatelia-Campañas-1-a-r-2026---4-may-2026 (1).csv", "rb") as f:
    content = f.read()

records = parse_meta_csv(content, "test.csv")
print("Found records:", len(records))
if records:
    print(records[0])
