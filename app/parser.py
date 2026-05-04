import openpyxl
from typing import List, Dict, Any

# Exact column names from Dropi XLSX → SQLite field names
COLUMN_MAP: Dict[str, str] = {
    "FECHA DE REPORTE":              "fecha_reporte",
    "ID":                            "id",
    "HORA":                          "hora",
    "FECHA":                         "fecha",
    "NOMBRE CLIENTE":                "nombre_cliente",
    "TELÉFONO":                      "telefono",
    "EMAIL":                         "email",
    "TIPO DE IDENTIFICACION":        "tipo_identificacion",
    "NRO DE IDENTIFICACION":         "nro_identificacion",
    "NÚMERO GUIA":                   "numero_guia",
    "ESTATUS":                       "estatus",
    "TIPO DE ENVIO":                 "tipo_envio",
    "DEPARTAMENTO DESTINO":          "departamento_destino",
    "CIUDAD DESTINO":                "ciudad_destino",
    "DIRECCION":                     "direccion",
    "NOTAS":                         "notas",
    "TRANSPORTADORA":                "transportadora",
    "TOTAL DE LA ORDEN":             "total_orden",
    "GANANCIA":                      "ganancia",
    "PRECIO FLETE":                  "precio_flete",
    "COSTO DEVOLUCION FLETE":        "costo_devolucion_flete",
    "COMISION":                      "comision",
    "% COMISION DE LA PLATAFORMMA":  "pct_comision",
    "PRECIO PROVEEDOR":              "precio_proveedor",
    "PRECIO PROVEEDOR X CANTIDAD":   "precio_proveedor_x_cantidad",
    "PRODUCTO ID":                   "producto_id",
    "SKU":                           "sku",
    "VARIACION ID":                  "variacion_id",
    "PRODUCTO":                      "producto",
    "VARIACION":                     "variacion",
    "CANTIDAD":                      "cantidad",
    "NOVEDAD":                       "novedad",
    "FUE SOLUCIONADA LA NOVEDAD":    "novedad_solucionada",
    "HORA DE NOVEDAD":               "hora_novedad",
    "FECHA DE NOVEDAD":              "fecha_novedad",
    "SOLUCIÓN":                      "solucion",
    "HORA DE SOLUCIÓN":              "hora_solucion",
    "FECHA DE SOLUCIÓN":             "fecha_solucion",
    "OBSERVACIÓN":                   "observacion",
    "HORA DE ÚLTIMO MOVIMIENTO":     "hora_ultimo_movimiento",
    "FECHA DE ÚLTIMO MOVIMIENTO":    "fecha_ultimo_movimiento",
    "ÚLTIMO MOVIMIENTO":             "ultimo_movimiento",
    "CONCEPTO ÚLTIMO MOVIMIENTO":    "concepto_ultimo_movimiento",
    "UBICACIÓN DE ÚLTIMO MOVIMIENTO":"ubicacion_ultimo_movimiento",
    "VENDEDOR":                      "vendedor",
    "TIPO DE TIENDA":                "tipo_tienda",
    "TIENDA":                        "tienda",
    "ID DE ORDEN DE TIENDA":         "id_orden_tienda",
    "NUMERO DE PEDIDO DE TIENDA":    "numero_pedido_tienda",
    "TAGS":                          "tags",
    "FECHA GUIA GENERADA":           "fecha_guia_generada",
    "CONTADOR DE INDEMNIZACIONES":   "contador_indemnizaciones",
    "CONCEPTO ÚLTIMA INDENMIZACIÓN": "concepto_ultima_indemnizacion",
}


def _normalize_date(value) -> "Optional[str]":
    """Convert DD-MM-YYYY to YYYY-MM-DD for SQLite date ordering."""
    if not value:
        return None
    s = str(value).strip()
    if len(s) == 10 and s[2] == "-":
        # DD-MM-YYYY → YYYY-MM-DD
        d, m, y = s.split("-")
        return f"{y}-{m}-{d}"
    return s


def parse_xlsx(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parse Dropi XLSX bytes → list of dicts ready for SQLite upsert."""
    import io
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return []

    raw_headers = rows[0]
    # Build index: db_field → column_index (skip unknown columns)
    col_index: Dict[str, int] = {}
    for i, h in enumerate(raw_headers):
        if h and str(h).strip() in COLUMN_MAP:
            db_field = COLUMN_MAP[str(h).strip()]
            col_index[db_field] = i

    date_fields = {
        "fecha_reporte", "fecha", "fecha_novedad",
        "fecha_solucion", "fecha_ultimo_movimiento", "fecha_guia_generada",
    }

    records = []
    for row in rows[1:]:
        if not any(row):
            continue
        rec: Dict[str, Any] = {"source_file": filename}
        for field, idx in col_index.items():
            val = row[idx] if idx < len(row) else None
            if field in date_fields:
                val = _normalize_date(val)
            rec[field] = val
        # Must have an id to upsert
        if rec.get("id") is not None:
            records.append(rec)

    return records


def upsert_records(conn, records: List[Dict[str, Any]]) -> int:
    """INSERT OR REPLACE all records. Returns count inserted/updated."""
    if not records:
        return 0

    all_fields = list({k for r in records for k in r.keys()})
    placeholders = ", ".join(["?" for _ in all_fields])
    cols = ", ".join(all_fields)
    sql = f"INSERT OR REPLACE INTO orders ({cols}) VALUES ({placeholders})"

    data = []
    for rec in records:
        data.append(tuple(rec.get(f) for f in all_fields))

    conn.executemany(sql, data)
    conn.commit()
    return len(records)


def parse_meta_csv(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parse Meta Ads CSV bytes → list of dicts for meta_ads_spend table."""
    import csv
    import io
    
    text = file_bytes.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    
    records = []
    for row in reader:
        # Check if this row looks like a Meta Ads row
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


def upsert_meta_spend(conn, records: List[Dict[str, Any]]) -> int:
    """INSERT OR REPLACE meta ads spend. Returns count inserted/updated."""
    if not records:
        return 0

    sql = """
        INSERT OR REPLACE INTO meta_ads_spend 
        (fecha, campaign_name, spend, results) 
        VALUES (?, ?, ?, ?)
    """
    
    data = [(r["fecha"], r["campaign_name"], r["spend"], r["results"]) for r in records]
    conn.executemany(sql, data)
    conn.commit()
    return len(records)

