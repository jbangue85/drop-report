import sqlite3
import os
from datetime import datetime, time, timedelta
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
FINALIZED     = ("ENTREGADO", "CANCELADO", "DEVOLUCION", "DEVOLUCION EN BODEGA")
STALE_BUSINESS_HOURS = 48


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


def _action_text_blob(alias: str = "o") -> str:
    return (
        f"upper(COALESCE({alias}.ultimo_movimiento, '') || ' ' || "
        f"COALESCE({alias}.concepto_ultimo_movimiento, '') || ' ' || "
        f"COALESCE({alias}.ubicacion_ultimo_movimiento, '') || ' ' || "
        f"COALESCE({alias}.novedad, ''))"
    )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _business_hours_elapsed(start_value: Optional[str], end_value: Optional[str]) -> float:
    start = _parse_datetime(start_value)
    end = _parse_datetime(end_value)
    if not start or not end or end <= start:
        return 0.0

    total_seconds = 0.0
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5:
            day_start = datetime.combine(day, time.min)
            day_end = day_start + timedelta(days=1)
            overlap_start = max(start, day_start)
            overlap_end = min(end, day_end)
            if overlap_end > overlap_start:
                total_seconds += (overlap_end - overlap_start).total_seconds()
        day += timedelta(days=1)

    return total_seconds / 3600


def _ensure_business_hours_function(conn: sqlite3.Connection):
    conn.create_function("business_hours_elapsed", 2, _business_hours_elapsed)


def _stale_predicate(alias: str = "o", reference_now: Optional[str] = None) -> tuple[str, list]:
    movement_dt = (
        f"datetime({alias}.fecha_ultimo_movimiento || ' ' || "
        f"COALESCE({alias}.hora_ultimo_movimiento, '00:00:00'))"
    )
    final_statuses = ",".join(f"'{s}'" for s in FINALIZED)
    if reference_now:
        return (
            f"{alias}.estatus NOT IN ({final_statuses}) AND "
            f"{alias}.fecha_ultimo_movimiento IS NOT NULL AND "
            f"business_hours_elapsed({movement_dt}, ?) >= {STALE_BUSINESS_HOURS}",
            [reference_now],
        )
    return (
        f"{alias}.estatus NOT IN ({final_statuses}) AND "
        f"{alias}.fecha_ultimo_movimiento IS NOT NULL AND "
        f"business_hours_elapsed({movement_dt}, datetime('now')) >= {STALE_BUSINESS_HOURS}",
        [],
    )


def _pending_office_predicate(alias: str = "o") -> str:
    text_blob = _action_text_blob(alias)
    patterns = (
        "%RECLAMAR EN OFICINA%",
        "%PENDIENTE POR RECIBIR EN OFICINA%",
        "%RECIBIR EN OFICINA%",
        "%RETIRO EN OFICINA%",
        "%RECOGER EN OFICINA%",
        "%DISPONIBLE PARA RECOGER%",
        "%COORDINAR LA ENTREGA%",
        "%NO HAY QUIEN RECIBA%",
    )
    conditions = " OR ".join(f"{text_blob} LIKE '{pattern}'" for pattern in patterns)
    final_statuses = ",".join(f"'{s}'" for s in FINALIZED)
    return f"{alias}.estatus NOT IN ({final_statuses}) AND ({conditions})"


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _attention_rule_predicate(conn: sqlite3.Connection, alias: str = "o", category: Optional[str] = None) -> str:
    if not _table_exists(conn, "attention_rules"):
        return _pending_office_predicate(alias)

    text_blob = _action_text_blob(alias)
    category_filter = f"AND ar.category = '{category}'" if category else ""
    final_statuses = ",".join(f"'{s}'" for s in FINALIZED)
    return f"""
        {alias}.estatus NOT IN ({final_statuses})
        AND EXISTS (
            SELECT 1
            FROM attention_rules ar
            WHERE ar.active = 1
              AND ar.requires_call = 1
              {category_filter}
              AND (
                ar.transportadora IS NULL
                OR upper(ar.transportadora) = upper(COALESCE({alias}.transportadora, ''))
              )
              AND (
                (ar.match_scope = 'estatus' AND upper(COALESCE({alias}.estatus, '')) LIKE '%' || upper(ar.match_text) || '%')
                OR (ar.match_scope = 'novedad' AND upper(COALESCE({alias}.novedad, '')) LIKE '%' || upper(ar.match_text) || '%')
                OR (ar.match_scope = 'movement' AND {text_blob} LIKE '%' || upper(ar.match_text) || '%')
                OR (ar.match_scope = 'any' AND {text_blob} LIKE '%' || upper(ar.match_text) || '%')
              )
        )
    """


def _action_predicate(conn: sqlite3.Connection, alias: str = "o", reference_now: Optional[str] = None) -> tuple[str, list]:
    _ensure_business_hours_function(conn)
    stale_sql, stale_params = _stale_predicate(alias, reference_now)
    rules_sql = _attention_rule_predicate(conn, alias)
    base_statuses = ",".join(f"'{s}'" for s in NEEDS_ACTION)
    predicate = f"({alias}.estatus IN ({base_statuses}) OR {stale_sql} OR {rules_sql})"
    return predicate, stale_params


KNOWN_ORDER_MARGIN_SQL = """
    CASE
        WHEN ganancia IS NOT NULL THEN ganancia
        ELSE total_orden - COALESCE(precio_proveedor_x_cantidad, 0) - COALESCE(precio_flete, 0)
    END
"""

PROJECTED_ORDER_MARGIN_SQL = f"""
    CASE
        WHEN estatus = 'CANCELADO' THEN 0
        WHEN estatus IN ('DEVOLUCION', 'DEVOLUCION EN BODEGA') THEN -COALESCE(precio_proveedor_x_cantidad, 0) - COALESCE(precio_flete, 0) - COALESCE(costo_devolucion_flete, 0)
        ELSE {KNOWN_ORDER_MARGIN_SQL}
    END
"""

CONFIRMED_ORDER_MARGIN_SQL = f"""
    CASE
        WHEN estatus = 'ENTREGADO' THEN {KNOWN_ORDER_MARGIN_SQL}
        WHEN estatus IN ('DEVOLUCION', 'DEVOLUCION EN BODEGA') THEN -COALESCE(precio_proveedor_x_cantidad, 0) - COALESCE(precio_flete, 0) - COALESCE(costo_devolucion_flete, 0)
        ELSE 0
    END
"""


# ── KPIs ─────────────────────────────────────────────────────────────────────

def calc_kpis(conn: sqlite3.Connection, date_from=None, date_to=None, estatus=None, reference_now: Optional[str] = None) -> dict:
    where, params = _where(date_from, date_to, estatus)
    action_sql, action_params = _action_predicate(conn, "orders", reference_now)
    row = conn.execute(f"""
        SELECT
            COALESCE(SUM(total_orden), 0)                                          AS ingresos_brutos,
            COALESCE(SUM({CONFIRMED_ORDER_MARGIN_SQL}), 0)                         AS ganancia_real,
            COALESCE(SUM({PROJECTED_ORDER_MARGIN_SQL}), 0)                         AS ganancia_proyectada,
            COUNT(*)                                                                AS volumen_pedidos,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END)                      AS entregados,
            COUNT(CASE WHEN estatus = 'CANCELADO' THEN 1 END)                      AS cancelados,
            COUNT(CASE WHEN estatus IN ('DEVOLUCION', 'DEVOLUCION EN BODEGA') THEN 1 END) AS devoluciones,
            COUNT(CASE WHEN estatus NOT IN ('ENTREGADO', 'CANCELADO', 'DEVOLUCION', 'DEVOLUCION EN BODEGA') THEN 1 END) AS en_curso_logistico,
            COUNT(CASE WHEN {action_sql} THEN 1 END)                               AS requieren_accion,
            ROUND(
                COUNT(CASE WHEN estatus = 'CANCELADO' THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0),
                1
            )                                                                       AS tasa_cancelacion,
            ROUND(
                COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) * 100.0
                / NULLIF(COUNT(CASE WHEN estatus IN (
                    'ENTREGADO','DEVOLUCION','DEVOLUCION EN BODEGA'
                ) THEN 1 END), 0),
                1
            )                                                                       AS tasa_entrega,
            ROUND(
                COUNT(CASE WHEN estatus IN ('DEVOLUCION', 'DEVOLUCION EN BODEGA') THEN 1 END) * 100.0
                / NULLIF(COUNT(CASE WHEN estatus IN (
                    'ENTREGADO','DEVOLUCION','DEVOLUCION EN BODEGA'
                ) THEN 1 END), 0),
                1
            )                                                                       AS tasa_devolucion,
            ROUND(
                COUNT(CASE WHEN estatus IN ('ENTREGADO','DEVOLUCION','DEVOLUCION EN BODEGA') THEN 1 END) * 100.0
                / NULLIF(COUNT(CASE WHEN estatus != 'CANCELADO' THEN 1 END), 0),
                1
            )                                                                       AS tasa_cierre_logistico
        FROM orders {where}
    """, action_params + params).fetchone()

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
            COALESCE(SUM({PROJECTED_ORDER_MARGIN_SQL}), 0) AS ganancia,
            COUNT(CASE WHEN estatus = 'ENTREGADO' THEN 1 END) AS entregados,
            COUNT(CASE WHEN estatus IN ('DESPACHADA', 'EN REPARTO', 'EN ESPERA DE RUTA DOMESTICA', 'ENTREGADO', 'DEVOLUCION', 'NOVEDAD', 'EN BODEGA TRANSPORTADORA', 'EN REEXPEDICION', 'GUIA_GENERADA', 'PREPARADO PARA TRANSPORTADORA') THEN 1 END) AS despachados,
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
        # Use despachados as denominator for a more realistic daily progress view
        tasa = round((r["entregados"] * 100.0 / r["despachados"]), 1) if r["despachados"] > 0 else 0
        results[fecha] = {
            "fecha": fecha,
            "pedidos": r["pedidos"],
            "ingresos": r["ingresos"],
            "ganancia": r["ganancia"] - spend_dict.get(fecha, 0),
            "tasa_entrega": tasa,
            "entregados": r["entregados"],
            "despachados": r["despachados"]
        }
        
    for r in spend_rows:
        fecha = r["fecha"]
        if fecha not in results:
            results[fecha] = {
                "fecha": fecha,
                "pedidos": 0,
                "ingresos": 0,
                "ganancia": -r["spend"],
                "tasa_entrega": 0,
                "entregados": 0,
                "despachados": 0
            }
            
    return sorted(list(results.values()), key=lambda x: x["fecha"], reverse=False)


def calc_daily_control(conn, date_from=None, date_to=None) -> list:
    where, params = _where(date_from, date_to)
    orders_query = f"""
        SELECT
            fecha,
            COALESCE(producto, 'Sin Producto') AS producto,
            COUNT(*) AS ventas_dia,
            COUNT(CASE WHEN estatus = 'CANCELADO' THEN 1 END) AS ventas_canceladas
        FROM orders {where}
        GROUP BY fecha, COALESCE(producto, 'Sin Producto')
    """
    orders_rows = conn.execute(orders_query, params).fetchall()

    spend_where = where.replace("fecha", "s.fecha") if where else ""
    spend_query = f"""
        SELECT
            s.fecha,
            COALESCE(m.producto, 'Otros/Sin Asignar') AS producto,
            COALESCE(SUM(s.spend), 0) as spend
        FROM meta_ads_spend s
        LEFT JOIN campaign_map m ON s.campaign_name = m.campaign_name
        {spend_where}
        GROUP BY s.fecha, COALESCE(m.producto, 'Otros/Sin Asignar')
    """
    spend_rows = conn.execute(spend_query, params).fetchall()

    config_rows = conn.execute("""
        SELECT producto, pct_devolucion, flete_base_dev, precio_venta, costo_proveedor
        FROM product_projection_config
    """).fetchall()
    config_map = {r["producto"]: dict(r) for r in config_rows}

    fallback_rows = conn.execute("""
        SELECT
            COALESCE(producto, 'Sin Producto') AS producto,
            AVG(CASE
                WHEN cantidad IS NOT NULL AND cantidad > 0 THEN total_orden * 1.0 / cantidad
                ELSE total_orden
            END) AS precio_venta,
            AVG(CASE
                WHEN cantidad IS NOT NULL AND cantidad > 0 THEN precio_proveedor_x_cantidad * 1.0 / cantidad
                ELSE precio_proveedor_x_cantidad
            END) AS costo_proveedor,
            AVG(precio_flete) AS flete_base_dev
        FROM orders
        GROUP BY COALESCE(producto, 'Sin Producto')
    """).fetchall()
    fallback_map = {r["producto"]: dict(r) for r in fallback_rows}

    iva_factor = _get_iva_factor()
    spend_dict = {(r["fecha"], r["producto"]): r["spend"] * iva_factor for r in spend_rows}

    def resolve_projection_inputs(producto: str) -> dict:
        config = config_map.get(producto, {})
        fallback = fallback_map.get(producto, {})

        pct_devolucion = config.get("pct_devolucion")
        if pct_devolucion is None:
            pct_devolucion = 0.25

        flete_base_dev = config.get("flete_base_dev")
        if flete_base_dev is None:
            flete_base_dev = fallback.get("flete_base_dev") or 0

        precio_venta = config.get("precio_venta")
        if precio_venta is None:
            precio_venta = fallback.get("precio_venta") or 0

        costo_proveedor = config.get("costo_proveedor")
        if costo_proveedor is None:
            costo_proveedor = fallback.get("costo_proveedor") or 0

        return {
            "pct_devolucion": pct_devolucion,
            "flete_base_dev": flete_base_dev,
            "precio_venta": precio_venta,
            "costo_proveedor": costo_proveedor,
        }

    results = {}
    for r in orders_rows:
        fecha = r["fecha"]
        producto = r["producto"]
        key = (fecha, producto)
        inputs = resolve_projection_inputs(producto)

        ventas_dia = r["ventas_dia"] or 0
        ventas_canceladas = r["ventas_canceladas"] or 0
        pct_cancelado = (ventas_canceladas / ventas_dia) if ventas_dia > 0 else 0
        pct_devolucion = inputs["pct_devolucion"] or 0
        flete_con_dev = (
            inputs["flete_base_dev"] / (1 - pct_devolucion)
            if pct_devolucion < 1 else 0
        )
        ventas_efectivas = ventas_dia * (1 - (pct_cancelado + pct_devolucion))
        spend = spend_dict.get(key, 0)
        cpa = (spend / ventas_efectivas) if ventas_efectivas > 0 else 0
        utilidad_unitaria = (
            inputs["precio_venta"] - flete_con_dev - inputs["costo_proveedor"] - cpa
        )
        utilidad_total = utilidad_unitaria * ventas_efectivas
        roi = (utilidad_total / spend) if spend > 0 else 0

        results[key] = {
            "fecha": fecha,
            "producto": producto,
            "ventas_dia": ventas_dia,
            "ventas_canceladas": ventas_canceladas,
            "pct_cancelado": pct_cancelado,
            "pct_devolucion": pct_devolucion,
            "ventas_efectivas": ventas_efectivas,
            "ad_spend": spend,
            "cpa": cpa,
            "precio_venta": inputs["precio_venta"],
            "costo_proveedor": inputs["costo_proveedor"],
            "flete_base_dev": inputs["flete_base_dev"],
            "flete_con_dev": flete_con_dev,
            "utilidad_unitaria": utilidad_unitaria,
            "utilidad_total": utilidad_total,
            "roi": roi,
        }

    for r in spend_rows:
        fecha = r["fecha"]
        producto = r["producto"]
        key = (fecha, producto)
        if key in results:
            continue

        inputs = resolve_projection_inputs(producto)
        pct_devolucion = inputs["pct_devolucion"] or 0
        flete_con_dev = (
            inputs["flete_base_dev"] / (1 - pct_devolucion)
            if pct_devolucion < 1 else 0
        )
        spend = (r["spend"] or 0) * iva_factor

        results[key] = {
            "fecha": fecha,
            "producto": producto,
            "ventas_dia": 0,
            "ventas_canceladas": 0,
            "pct_cancelado": 0,
            "pct_devolucion": pct_devolucion,
            "ventas_efectivas": 0,
            "ad_spend": spend,
            "cpa": 0,
            "precio_venta": inputs["precio_venta"],
            "costo_proveedor": inputs["costo_proveedor"],
            "flete_base_dev": inputs["flete_base_dev"],
            "flete_con_dev": flete_con_dev,
            "utilidad_unitaria": inputs["precio_venta"] - flete_con_dev - inputs["costo_proveedor"],
            "utilidad_total": -spend,
            "roi": -1 if spend > 0 else 0,
        }

    return sorted(list(results.values()), key=lambda x: (x["fecha"], x["producto"]), reverse=True)


def get_projection_configs(conn) -> list:
    rows = conn.execute("""
        WITH products AS (
            SELECT DISTINCT COALESCE(producto, 'Sin Producto') AS producto FROM orders
            UNION
            SELECT producto FROM product_projection_config
            UNION
            SELECT DISTINCT COALESCE(producto, 'Otros/Sin Asignar') AS producto FROM campaign_map
        ),
        fallback AS (
            SELECT
                COALESCE(producto, 'Sin Producto') AS producto,
                AVG(CASE
                    WHEN cantidad IS NOT NULL AND cantidad > 0 THEN total_orden * 1.0 / cantidad
                    ELSE total_orden
                END) AS precio_venta,
                AVG(CASE
                    WHEN cantidad IS NOT NULL AND cantidad > 0 THEN precio_proveedor_x_cantidad * 1.0 / cantidad
                    ELSE precio_proveedor_x_cantidad
                END) AS costo_proveedor,
                AVG(precio_flete) AS flete_base_dev
            FROM orders
            GROUP BY COALESCE(producto, 'Sin Producto')
        )
        SELECT
            p.producto,
            cfg.pct_devolucion,
            cfg.flete_base_dev,
            cfg.precio_venta,
            cfg.costo_proveedor,
            COALESCE(cfg.pct_devolucion, 0.25) AS effective_pct_devolucion,
            COALESCE(cfg.flete_base_dev, fallback.flete_base_dev, 0) AS effective_flete_base_dev,
            COALESCE(cfg.precio_venta, fallback.precio_venta, 0) AS effective_precio_venta,
            COALESCE(cfg.costo_proveedor, fallback.costo_proveedor, 0) AS effective_costo_proveedor,
            CASE WHEN cfg.producto IS NULL THEN 0 ELSE 1 END AS has_custom_config
        FROM products p
        LEFT JOIN product_projection_config cfg ON cfg.producto = p.producto
        LEFT JOIN fallback ON fallback.producto = p.producto
        WHERE p.producto IS NOT NULL
        ORDER BY p.producto
    """).fetchall()
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

def get_action_orders(conn, date_from=None, date_to=None, reference_now: Optional[str] = None) -> list:
    """Orders needing agent action: pending confirmation, novelties, stale logistics, office receipt follow-up."""
    action_sql, action_params = _action_predicate(conn, "o", reference_now)
    where, params = _where(date_from, date_to, extra=action_sql)
    stale_sql, stale_params = _stale_predicate("o", reference_now)
    rule_sql = _attention_rule_predicate(conn, "o")
    office_sql = _attention_rule_predicate(conn, "o", category="office_pickup")
    base_statuses = ",".join(f"'{s}'" for s in NEEDS_ACTION)
    rows = conn.execute(f"""
        SELECT
            o.id, o.fecha, o.hora, o.estatus,
            o.nombre_cliente, o.telefono,
            o.producto, o.variacion, o.cantidad,
            o.ciudad_destino, o.departamento_destino, o.direccion,
            o.transportadora, o.numero_guia,
            o.novedad, o.total_orden, o.notas,
            o.fecha_ultimo_movimiento, o.hora_ultimo_movimiento,
            o.ultimo_movimiento, o.concepto_ultimo_movimiento, o.ubicacion_ultimo_movimiento,
            CASE WHEN {stale_sql} THEN 1 ELSE 0 END AS sin_movimiento_48h,
            CASE WHEN {rule_sql} THEN 1 ELSE 0 END AS regla_atencion,
            CASE WHEN {office_sql} THEN 1 ELSE 0 END AS pendiente_recibir_oficina,
            CASE WHEN o.estatus IN ({base_statuses}) OR {rule_sql} THEN 1 ELSE 0 END AS requiere_llamada,
            CASE
                WHEN o.estatus IN ({base_statuses}) OR {rule_sql} THEN 'llamada'
                WHEN {stale_sql} THEN 'soporte'
                ELSE 'gestion'
            END AS tipo_gestion,
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
            WHERE resultado IN ('CONTACTADO', 'NO_CONTESTO', 'BUZON', 'SOLUCIONADO', 'DEVOLUCION', 'OTRO')
            GROUP BY order_id
        ) cn_count ON cn_count.order_id = o.id
        {where}
        ORDER BY sin_movimiento_48h DESC, pendiente_recibir_oficina DESC, o.estatus, o.fecha DESC
    """, stale_params + stale_params + params + action_params).fetchall()
    return [dict(r) for r in rows]


def get_filter_options(conn) -> dict:
    estatus_rows = conn.execute("SELECT DISTINCT estatus FROM orders WHERE estatus IS NOT NULL ORDER BY estatus").fetchall()
    date_row = conn.execute("SELECT MIN(fecha) AS min_date, MAX(fecha) AS max_date FROM orders").fetchone()
    return {
        "estatus": [r["estatus"] for r in estatus_rows],
        "min_date": date_row["min_date"],
        "max_date": date_row["max_date"],
    }
