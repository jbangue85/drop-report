from dotenv import load_dotenv
load_dotenv()  # Load .env before anything reads os.getenv()

import os
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .database import get_db, init_db, seed_admin_user
from .parser import parse_xlsx, upsert_records
from .analytics import (
    calc_kpis,
    calc_status_distribution,
    calc_daily_trend,
    calc_product_ranking,
    calc_carrier_performance,
    get_projection_configs,
    get_action_orders,
    get_filter_options,
)
from .auth import hash_password, verify_password, create_token, decode_token

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Drop Report API", docs_url="/api/docs")
security = HTTPBearer()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.on_event("startup")
def startup():
    init_db()
    # Seed default admin from env vars (set in docker-compose)
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "dropi2024")
    seed_admin_user(admin_user, hash_password(admin_pass))


# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return payload


def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return user


# ── Auth routes ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginRequest):
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash, role FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    conn.close()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_token(body.username, row["role"])
    return {"access_token": token, "token_type": "bearer", "role": row["role"]}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ProjectionConfigRequest(BaseModel):
    producto: str
    pct_devolucion: float
    flete_base_dev: float
    precio_venta: float
    costo_proveedor: float


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordRequest, user=Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", (user["sub"],)
    ).fetchone()
    if not row or not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (hash_password(body.new_password), user["sub"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Upload routes ─────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xlsx o .csv")
    content = await file.read()
    
    conn = get_db()
    
    if file.filename.lower().endswith(".csv"):
        from app.parser import parse_meta_csv, upsert_meta_spend
        records = parse_meta_csv(content, file.filename)
        if not records:
            raise HTTPException(status_code=422, detail="El CSV no contiene datos válidos de Meta Ads")
        count = upsert_meta_spend(conn, records)
    else:
        from app.parser import parse_xlsx, upsert_records
        records = parse_xlsx(content, file.filename)
        if not records:
            raise HTTPException(status_code=422, detail="El archivo Excel no contiene datos válidos")
        count = upsert_records(conn, records)

    conn.execute(
        "INSERT INTO uploads (filename, rows_upserted) VALUES (?, ?)",
        (file.filename, count),
    )
    conn.commit()
    conn.close()
    return {"filename": file.filename, "rows_upserted": count}


@app.get("/api/uploads")
def list_uploads(user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT filename, rows_upserted, uploaded_at FROM uploads ORDER BY uploaded_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Dashboard routes ──────────────────────────────────────────────────────────

def common_filters(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    estatus: Optional[List[str]] = Query(None),
):
    return {"date_from": date_from, "date_to": date_to, "estatus": estatus}


@app.get("/api/kpis")
def kpis(filters=Depends(common_filters), user=Depends(get_current_user)):
    conn = get_db()
    result = calc_kpis(conn, **filters)
    conn.close()
    return result


@app.get("/api/charts/status")
def chart_status(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_status_distribution(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/trend")
def chart_trend(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_daily_trend(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/daily-control")
def daily_control(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    from app.analytics import calc_daily_control
    conn = get_db()
    result = calc_daily_control(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/products")
def chart_products(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_product_ranking(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/carriers")
def chart_carriers(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_carrier_performance(conn, date_from, date_to)
    conn.close()
    return result

@app.get("/api/mappings")
def get_mappings(user=Depends(get_current_user)):
    conn = get_db()
    
    # Get all campaigns from meta_ads_spend and their mapped product
    query = """
        SELECT DISTINCT s.campaign_name, m.producto 
        FROM meta_ads_spend s
        LEFT JOIN campaign_map m ON s.campaign_name = m.campaign_name
        ORDER BY s.campaign_name
    """
    mappings = [dict(r) for r in conn.execute(query).fetchall()]
    
    # Get all unique products from orders
    products = [r["producto"] for r in conn.execute("SELECT DISTINCT producto FROM orders WHERE producto IS NOT NULL ORDER BY producto").fetchall()]
    
    conn.close()
    return {"mappings": mappings, "products": products}

@app.post("/api/mappings")
async def save_mapping(
    request: Request,
    user=Depends(get_current_user)
):
    data = await request.json()
    campaign_name = data.get("campaign_name")
    producto = data.get("producto")
    
    if not campaign_name:
        raise HTTPException(status_code=400, detail="Falta campaign_name")
        
    conn = get_db()
    if producto:
        conn.execute("INSERT OR REPLACE INTO campaign_map (campaign_name, producto) VALUES (?, ?)", (campaign_name, producto))
    else:
        conn.execute("DELETE FROM campaign_map WHERE campaign_name = ?", (campaign_name,))
    conn.commit()
    conn.close()
    return {"status": "ok"}



@app.get("/api/filters/options")
def filter_options(user=Depends(get_current_user)):
    conn = get_db()
    result = get_filter_options(conn)
    conn.close()
    return result


@app.get("/api/projection-configs")
def projection_configs(user=Depends(get_current_user)):
    conn = get_db()
    result = get_projection_configs(conn)
    conn.close()
    return result


@app.post("/api/projection-configs")
def save_projection_config(body: ProjectionConfigRequest, admin=Depends(require_admin)):
    producto = body.producto.strip()
    if not producto:
        raise HTTPException(status_code=400, detail="Falta producto")
    if body.pct_devolucion < 0 or body.pct_devolucion >= 1:
        raise HTTPException(status_code=400, detail="pct_devolucion debe estar entre 0 y 1")

    conn = get_db()
    conn.execute(
        """
        INSERT INTO product_projection_config
            (producto, pct_devolucion, flete_base_dev, precio_venta, costo_proveedor, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(producto) DO UPDATE SET
            pct_devolucion = excluded.pct_devolucion,
            flete_base_dev = excluded.flete_base_dev,
            precio_venta = excluded.precio_venta,
            costo_proveedor = excluded.costo_proveedor,
            updated_at = datetime('now')
        """,
        (
            producto,
            body.pct_devolucion,
            body.flete_base_dev,
            body.precio_venta,
            body.costo_proveedor,
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "producto": producto}


# ── Call Center routes ────────────────────────────────────────────────────────

@app.get("/api/calls/pending")
def calls_pending(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = get_action_orders(conn, date_from, date_to)
    conn.close()
    return result


class CallNoteRequest(BaseModel):
    order_id: int
    resultado: str   # CONTACTADO | NO_CONTESTO | BUZON | SOLUCIONADO | DEVOLUCION | OTRO
    notas: Optional[str] = None


@app.post("/api/calls/notes")
def save_call_note(body: CallNoteRequest, user=Depends(get_current_user)):
    valid = {"CONTACTADO", "NO_CONTESTO", "BUZON", "SOLUCIONADO", "DEVOLUCION", "OTRO"}
    if body.resultado not in valid:
        raise HTTPException(status_code=400, detail=f"resultado debe ser uno de: {valid}")
    conn = get_db()
    conn.execute(
        "INSERT INTO call_notes (order_id, agent, resultado, notas) VALUES (?, ?, ?, ?)",
        (body.order_id, user["sub"], body.resultado, body.notas),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/calls/notes/{order_id}")
def get_call_notes(order_id: int, user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM call_notes WHERE order_id = ? ORDER BY called_at DESC",
        (order_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Users management (admin only) ─────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "agent"


@app.post("/api/users")
def create_user(body: CreateUserRequest, admin=Depends(require_admin)):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (body.username, hash_password(body.password), body.role),
        )
        conn.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    finally:
        conn.close()
    return {"ok": True, "username": body.username}


@app.get("/api/users")
def list_users(admin=Depends(require_admin)):
    conn = get_db()
    rows = conn.execute("SELECT id, username, role FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Serve frontend ─────────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
