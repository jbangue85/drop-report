import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "/data/dropreport.db")

CREATE_ORDERS = """
CREATE TABLE IF NOT EXISTS orders (
    id                          INTEGER PRIMARY KEY,
    fecha_reporte               TEXT,
    hora                        TEXT,
    fecha                       TEXT,
    nombre_cliente              TEXT,
    telefono                    TEXT,
    email                       TEXT,
    tipo_identificacion         TEXT,
    nro_identificacion          TEXT,
    numero_guia                 TEXT,
    estatus                     TEXT,
    tipo_envio                  TEXT,
    departamento_destino        TEXT,
    ciudad_destino              TEXT,
    direccion                   TEXT,
    notas                       TEXT,
    transportadora              TEXT,
    total_orden                 REAL,
    ganancia                    REAL,
    precio_flete                REAL,
    costo_devolucion_flete      REAL,
    comision                    REAL,
    pct_comision                REAL,
    precio_proveedor            REAL,
    precio_proveedor_x_cantidad REAL,
    producto_id                 INTEGER,
    sku                         TEXT,
    variacion_id                TEXT,
    producto                    TEXT,
    variacion                   TEXT,
    cantidad                    INTEGER,
    novedad                     TEXT,
    novedad_solucionada         TEXT,
    hora_novedad                TEXT,
    fecha_novedad               TEXT,
    solucion                    TEXT,
    hora_solucion               TEXT,
    fecha_solucion              TEXT,
    observacion                 TEXT,
    hora_ultimo_movimiento      TEXT,
    fecha_ultimo_movimiento     TEXT,
    ultimo_movimiento           TEXT,
    concepto_ultimo_movimiento  TEXT,
    ubicacion_ultimo_movimiento TEXT,
    vendedor                    TEXT,
    tipo_tienda                 TEXT,
    tienda                      TEXT,
    id_orden_tienda             TEXT,
    numero_pedido_tienda        INTEGER,
    tags                        TEXT,
    fecha_guia_generada         TEXT,
    contador_indemnizaciones    INTEGER,
    concepto_ultima_indemnizacion TEXT,
    source_file                 TEXT,
    uploaded_at                 TEXT DEFAULT (datetime('now'))
);
"""

CREATE_UPLOADS = """
CREATE TABLE IF NOT EXISTS uploads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT NOT NULL,
    rows_upserted INTEGER,
    uploaded_at   TEXT DEFAULT (datetime('now'))
);
"""

CREATE_CALL_NOTES = """
CREATE TABLE IF NOT EXISTS call_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL,
    agent      TEXT NOT NULL,
    resultado  TEXT NOT NULL,   -- CONTACTADO, NO_CONTESTO, BUZÓN, SOLUCIONADO, DEVOLUCION
    notas      TEXT,
    called_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'agent'  -- admin | agent
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute(CREATE_ORDERS)
    conn.execute(CREATE_UPLOADS)
    conn.execute(CREATE_CALL_NOTES)
    conn.execute(CREATE_USERS)
    conn.commit()
    conn.close()


def seed_admin_user(username: str, password_hash: str):
    """Insert default admin if users table is empty."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            (username, password_hash),
        )
        conn.commit()
    conn.close()
