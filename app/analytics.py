import sqlite3
import os
from typing import Optional

def _get_iva_factor():
    try:
        return 1.0 + float(os.environ.get("ADS_IVA", "0"))
    except ValueError:
        return 1.0


# Status groups
DELIVERED     = ("ENTREGADO",)
ACTIVE        = ("DESPACHADA", "EN REPARTO", "EN ESPERA DE RUTA DOMESTICA")
NEEDS_ACTION  = ("PENDIENTE CONFIRMACION", "NOVEDAD")
CANCELLED     = ("CANCELADO",)
PENDING       = ("PENDIENTE",)


def _where(date_from=None, date_to=None, estatus=None, extra=""):
    conditions = []
    params: list = []
    if date_from:
        conditions.append("fecha >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("fecha <= ?")
        params.append(date_to)
    if estatus:
        ph = ",".join("?" * len(estatus))
        conditions.append(f"estatus IN ({ph})")
        params.extend(estatus)
    if extra:
        conditions.append(extra)
    clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return clause, params


# ── KPIs ─────────────────────────────────────────────────────────────────────

def calc_kpis(conn: sqlite3.Connection, date_from=None, date_to=None, estatus=None) -> dict:
    where, params = _where(date_from, date_to, estatus)
    row = conn.execute(f"""
        SELECT
            COALESCE(SUM(total_orden), 0)                                          AS ingresos_brutos,
            COALESCE(SUM(ganancia), 0)                                             AS ganancia_real,
            COALESCE(SUM(
                CASE WHEN ganancia IS NULL
                THEN total_orden - COALESCE(precio_proveedor_x_cantidad,0) - COALESCE(precio_flete,0)
                ELSE ganancia END
            ), 0)                                                                   AS ganancia_proyectada,
            COUNT(*)                                                                AS volumen_pedidos,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END)                      AS entregados,
            COUNT(CASE WHEN estatus IN ('PENDIENTE CONFIRMACION','NOVEDAD') THEN 1 END) AS requieren_accion,
            ROUND(
                COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) * 100.0
                / NULLIF(COUNT(CASE WHEN estatus IN (
                    'ENTREGADO','CANCELADO','DEVOLUCION','DEVOLUCION EN BODEGA'
                ) THEN 1 END), 0),
                1
            )                                                                       AS tasa_entrega
        FROM orders {where}
    """, params).fetchone()

    # Get ad spend (ignore estatus for ad spend)
    spend_where, spend_params = _where(date_from, date_to)
    spend_row = conn.execute(f"SELECT COALESCE(SUM(spend), 0) as total_spend FROM meta_ads_spend {spend_where}", spend_params).fetchone()
    raw_spend = spend_row["total_spend"] if spend_row else 0
    
    iva_factor = _get_iva_factor()
    total_spend = raw_spend * iva_factor

    kpis = dict(row) if row else {}
    if kpis:
        kpis["margen_bruto"] = kpis["ganancia_proyectada"] # Save raw margin
        kpis["ganancia_proyectada"] -= total_spend
        kpis["ganancia_real"] -= total_spend
        kpis["ad_spend"] = total_spend
        kpis["ads_iva"] = (iva_factor - 1.0) * 100
    return kpis


# ── Charts ───────────────────────────────────────────────────────────────────

def calc_status_distribution(conn, date_from=None, date_to=None) -> list:
    where, params = _where(date_from, date_to)
    rows = conn.execute(f"""
        SELECT estatus, COUNT(*) AS total
        FROM orders {where}
        GROUP BY estatus
        ORDER BY total DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def calc_daily_trend(conn, date_from=None, date_to=None) -> list:
    where, params = _where(date_from, date_to)
    orders_rows = conn.execute(f"""
        SELECT
            fecha,
            COUNT(*) AS pedidos,
            COALESCE(SUM(total_orden), 0) AS ingresos,
            COALESCE(SUM(
                CASE WHEN ganancia IS NULL
                THEN total_orden - COALESCE(precio_proveedor_x_cantidad,0) - COALESCE(precio_flete,0)
                ELSE ganancia END
            ), 0) AS ganancia,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) AS entregados,
            COUNT(CASE WHEN estatus IN ('ENTREGADO','CANCELADO','DEVOLUCION','DEVOLUCION EN BODEGA') THEN 1 END) AS finalizados
        FROM orders {where}
        GROUP BY fecha
    """, params).fetchall()
    
    spend_rows = conn.execute(f"SELECT fecha, COALESCE(SUM(spend), 0) as spend FROM meta_ads_spend {where} GROUP BY fecha", params).fetchall()
    iva_factor = _get_iva_factor()
    spend_dict = {r["fecha"]: r["spend"] * iva_factor for r in spend_rows}
    
    results = {}
    for r in orders_rows:
        fecha = r["fecha"]
        tasa = round((r["entregados"] * 100.0 / r["finalizados"]), 1) if r["finalizados"] > 0 else 0
        results[fecha] = {
            "fecha": fecha,
            "pedidos": r["pedidos"],
            "ingresos": r["ingresos"],
            "ganancia": r["ganancia"] - spend_dict.get(fecha, 0),
            "tasa_entrega": tasa
        }
        
    for r in spend_rows:
        fecha = r["fecha"]
        if fecha not in results:
            results[fecha] = {
                "fecha": fecha,
                "pedidos": 0,
                "ingresos": 0,
                "ganancia": -r["spend"],
                "tasa_entrega": 0
            }
            
    return sorted(list(results.values()), key=lambda x: x["fecha"], reverse=False)


def calc_daily_control(conn, date_from=None, date_to=None) -> list:
    where, params = _where(date_from, date_to)
    
    orders_query = f"""
        SELECT 
            fecha,
            COALESCE(producto, 'Sin Producto') AS producto,
            COUNT(*) AS total_pedidos,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) AS entregados,
            COUNT(CASE WHEN estatus = 'CANCELADO' THEN 1 END) AS cancelados,
            COUNT(CASE WHEN estatus = 'DEVOLUCION' THEN 1 END) AS devoluciones,
            COALESCE(SUM(total_orden), 0) AS ingresos_brutos,
            COALESCE(SUM(
                CASE WHEN ganancia IS NULL
                THEN total_orden - COALESCE(precio_proveedor_x_cantidad,0) - COALESCE(precio_flete,0)
                ELSE ganancia END
            ), 0) AS margen_bruto
        FROM orders {where}
        GROUP BY fecha, COALESCE(producto, 'Sin Producto')
    """
    orders_rows = conn.execute(orders_query, params).fetchall()
    
    spend_query = f"""
        SELECT 
            s.fecha, 
            COALESCE(m.producto, 'Otros/Sin Asignar') AS producto,
            COALESCE(SUM(s.spend), 0) as spend 
        FROM meta_ads_spend s
        LEFT JOIN campaign_map m ON s.campaign_name = m.campaign_name
        {where.replace('fecha', 's.fecha') if where else ''}
        GROUP BY s.fecha, COALESCE(m.producto, 'Otros/Sin Asignar')
    """
    spend_rows = conn.execute(spend_query, params).fetchall()
    
    # dict key is (fecha, producto)
    iva_factor = _get_iva_factor()
    spend_dict = {(r["fecha"], r["producto"]): r["spend"] * iva_factor for r in spend_rows}
    
    results = {}
    for r in orders_rows:
        fecha = r["fecha"]
        producto = r["producto"]
        key = (fecha, producto)
        
        spend = spend_dict.get(key, 0)
        margen = r["margen_bruto"]
        utilidad_total = margen - spend
        
        roi = (utilidad_total / spend) if spend > 0 else 0
        cpa = (spend / r["total_pedidos"]) if r["total_pedidos"] > 0 else 0
        
        results[key] = {
            "fecha": fecha,
            "producto": producto,
            "total_pedidos": r["total_pedidos"],
            "entregados": r["entregados"],
            "cancelados": r["cancelados"],
            "devoluciones": r["devoluciones"],
            "ingresos_brutos": r["ingresos_brutos"],
            "margen_bruto": margen,
            "ad_spend": spend,
            "cpa": cpa,
            "utilidad_total": utilidad_total,
            "roi": roi
        }
        
    for r in spend_rows:
        fecha = r["fecha"]
        producto = r["producto"]
        key = (fecha, producto)
        if key not in results:
            spend = r["spend"]
            results[key] = {
                "fecha": fecha,
                "producto": producto,
                "total_pedidos": 0, "entregados": 0, "cancelados": 0, "devoluciones": 0,
                "ingresos_brutos": 0, "margen_bruto": 0,
                "ad_spend": spend, "cpa": 0, "utilidad_total": -spend, "roi": -1
            }
            
    # Sort by date desc, then by total margin desc
    return sorted(list(results.values()), key=lambda x: (x["fecha"], x["margen_bruto"]), reverse=True)


def calc_product_ranking(conn, date_from=None, date_to=None, limit=15) -> list:
    where, params = _where(date_from, date_to)
    rows = conn.execute(f"""
        SELECT
            producto,
            SUM(cantidad)     AS unidades,
            COUNT(*)          AS pedidos,
            SUM(total_orden)  AS ingresos
        FROM orders {where}
        GROUP BY producto
        ORDER BY unidades DESC
        LIMIT {limit}
    """, params).fetchall()
    return [dict(r) for r in rows]


def calc_carrier_performance(conn, date_from=None, date_to=None) -> list:
    where, params = _where(date_from, date_to)
    rows = conn.execute(f"""
        SELECT
            transportadora,
            COUNT(*)                                                AS total,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END)      AS entregados,
            COUNT(CASE WHEN estatus = 'NOVEDAD' THEN 1 END)        AS novedades,
            ROUND(
                COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                                       AS tasa_entrega
        FROM orders {where}
        GROUP BY transportadora
        ORDER BY tasa_entrega DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


# ── Call Center ───────────────────────────────────────────────────────────────

def get_action_orders(conn, date_from=None, date_to=None) -> list:
    """Orders needing agent action: PENDIENTE CONFIRMACION + NOVEDAD."""
    where, params = _where(date_from, date_to, estatus=list(NEEDS_ACTION))
    rows = conn.execute(f"""
        SELECT
            o.id, o.fecha, o.hora, o.estatus,
            o.nombre_cliente, o.telefono,
            o.producto, o.variacion, o.cantidad,
            o.ciudad_destino, o.departamento_destino,
            o.transportadora, o.numero_guia,
            o.novedad, o.total_orden, o.notas,
            cn.resultado      AS ultima_gestion,
            cn.notas          AS nota_llamada,
            cn.agent          AS agente,
            cn.called_at      AS fecha_gestion,
            COALESCE(cn_count.intentos, 0) AS intentos
        FROM orders o
        LEFT JOIN (
            SELECT order_id, resultado, notas, agent, called_at
            FROM call_notes
            WHERE id IN (SELECT MAX(id) FROM call_notes GROUP BY order_id)
        ) cn ON cn.order_id = o.id
        LEFT JOIN (
            SELECT order_id, COUNT(*) as intentos
            FROM call_notes
            GROUP BY order_id
        ) cn_count ON cn_count.order_id = o.id
        {where}
        ORDER BY o.estatus, o.fecha DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_filter_options(conn) -> dict:
    estatus_rows = conn.execute("SELECT DISTINCT estatus FROM orders WHERE estatus IS NOT NULL ORDER BY estatus").fetchall()
    date_row = conn.execute("SELECT MIN(fecha) AS min_date, MAX(fecha) AS max_date FROM orders").fetchone()
    return {
        "estatus": [r["estatus"] for r in estatus_rows],
        "min_date": date_row["min_date"],
        "max_date": date_row["max_date"],
    }
