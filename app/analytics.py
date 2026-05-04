import sqlite3
from typing import Optional


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
                / NULLIF(COUNT(CASE WHEN estatus != 'PENDIENTE' AND estatus != 'PENDIENTE CONFIRMACION' THEN 1 END), 0),
                1
            )                                                                       AS tasa_entrega
        FROM orders {where}
    """, params).fetchone()

    return dict(row) if row else {}


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
    rows = conn.execute(f"""
        SELECT
            fecha,
            COUNT(*) AS pedidos,
            COALESCE(SUM(total_orden), 0) AS ingresos,
            COALESCE(SUM(
                CASE WHEN ganancia IS NULL
                THEN total_orden - COALESCE(precio_proveedor_x_cantidad,0) - COALESCE(precio_flete,0)
                ELSE ganancia END
            ), 0) AS ganancia
        FROM orders {where}
        GROUP BY fecha
        ORDER BY fecha ASC
    """, params).fetchall()
    return [dict(r) for r in rows]


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
